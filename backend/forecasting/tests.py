import tempfile
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from forecasting.models import ForecastRun, HourlyForecast
from shifts.models import Venue
from users.models import User


class ForecastingApiTests(APITestCase):
    """Пункты 12.4-12.9."""

    def setUp(self):
        self.password = "StrongPass123!"
        self.venue = Venue.objects.create(
            name="Ресторан Центральный",
            address="ул. Ленина, 1",
            timezone="Europe/Moscow",
        )
        self.other_venue = Venue.objects.create(
            name="Ресторан Парк",
            address="ул. Парковая, 7",
            timezone="Europe/Moscow",
        )
        self.manager = User.objects.create_user(
            username="manager_api",
            email="manager_api@example.com",
            password=self.password,
            first_name="Мария",
            last_name="Иванова",
            role=User.Role.MANAGER,
            venue=self.venue,
        )
        self.client.force_authenticate(user=self.manager)

    @staticmethod
    def _results(response):
        if isinstance(response.data, dict) and "results" in response.data:
            return response.data["results"]
        return response.data

    def test_12_4_upload_raw_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "forecasting.views.settings.ML_DATA_RAW",
            Path(tmp_dir),
        ):
            uploaded_file = self._fake_xlsx()

            response = self.client.post(
                reverse("forecast-upload-data"),
                {"file": uploaded_file},
                format="multipart",
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["detail"], "Файл загружен.")
            self.assertTrue(response.data["path"].endswith("real_orders.xlsx"))
            self.assertGreaterEqual(response.data["size_mb"], 0)

            saved_path = Path(response.data["path"])
            self.assertTrue(saved_path.exists())

    def test_12_5_run_ml_pipeline(self):
        def fake_execute(runner_self):
            run = runner_self.run
            now = timezone.now()
            run.status = ForecastRun.Status.COMPLETED
            run.accuracy_pct = 87.5
            run.mae = 3.2
            run.r2_score = 0.85
            run.started_at = now - timedelta(seconds=45.3)
            run.finished_at = now
            run.error_message = ""
            run.save()

        with patch(
            "forecasting.views.MLRunner.execute",
            autospec=True,
            side_effect=fake_execute,
        ), patch(
            "forecasting.views.load_forecast_to_db",
            return_value=48,
        ):
            response = self.client.post(
                reverse("forecast-run"),
                {"venue": self.venue.id},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["venue"], self.venue.id)
        self.assertEqual(response.data["venue_name"], self.venue.name)
        self.assertEqual(response.data["status"], ForecastRun.Status.COMPLETED)
        self.assertAlmostEqual(response.data["accuracy_pct"], 87.5, places=1)
        self.assertAlmostEqual(response.data["mae"], 3.2, places=1)
        self.assertAlmostEqual(response.data["r2_score"], 0.85, places=2)
        self.assertAlmostEqual(response.data["duration_seconds"], 45.3, places=1)

    def test_12_6_get_forecast_runs_list(self):
        own_run = ForecastRun.objects.create(
            venue=self.venue,
            triggered_by=self.manager,
            status=ForecastRun.Status.COMPLETED,
            accuracy_pct=82.0,
            mae=4.1,
            r2_score=0.74,
        )
        ForecastRun.objects.create(
            venue=self.other_venue,
            status=ForecastRun.Status.COMPLETED,
            accuracy_pct=90.0,
            mae=2.4,
            r2_score=0.91,
        )

        response = self.client.get(reverse("forecast-run-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], own_run.id)

    def test_12_7_get_daily_forecast(self):
        run = ForecastRun.objects.create(
            venue=self.venue,
            status=ForecastRun.Status.COMPLETED,
            make_forecast=True,
        )

        forecast_day = date(2026, 4, 2)
        HourlyForecast.objects.create(
            run=run,
            venue=self.venue,
            forecast_datetime=timezone.make_aware(datetime(2026, 4, 2, 10, 0)),
            date=forecast_day,
            hour=10,
            day_of_week=3,
            is_peak_hour=False,
            is_weekend=False,
            is_holiday=False,
            orders_predicted=10,
            orders_with_buffer=11,
            guests_predicted=20,
            guests_with_buffer=22,
        )
        HourlyForecast.objects.create(
            run=run,
            venue=self.venue,
            forecast_datetime=timezone.make_aware(datetime(2026, 4, 2, 18, 0)),
            date=forecast_day,
            hour=18,
            day_of_week=3,
            is_peak_hour=True,
            is_weekend=False,
            is_holiday=False,
            orders_predicted=15,
            orders_with_buffer=18,
            guests_predicted=30,
            guests_with_buffer=35,
        )

        response = self.client.get(
            reverse("forecast-daily"),
            {"venue": self.venue.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        day = response.data[0]
        self.assertEqual(str(day["date"]), "2026-04-02")
        self.assertAlmostEqual(day["total_orders"], 25.0, places=1)
        self.assertAlmostEqual(day["total_guests"], 50.0, places=1)
        self.assertAlmostEqual(day["morning_orders"], 10.0, places=1)
        self.assertAlmostEqual(day["evening_orders"], 15.0, places=1)
        self.assertAlmostEqual(day["peak_hour_orders"], 15.0, places=1)

    def test_12_8_get_model_accuracy(self):
        older_run = ForecastRun.objects.create(
            venue=self.venue,
            status=ForecastRun.Status.COMPLETED,
            train_model=True,
            accuracy_pct=81.0,
            mae=4.0,
            r2_score=0.73,
            finished_at=timezone.now() - timedelta(hours=2),
        )

        latest_run = ForecastRun.objects.create(
            venue=self.venue,
            status=ForecastRun.Status.COMPLETED,
            train_model=True,
            accuracy_pct=87.5,
            mae=3.2,
            r2_score=0.85,
            finished_at=timezone.now(),
        )

        # Избегаем недетерминизма в SQLite при одинаковом created_at.
        now = timezone.now()
        ForecastRun.objects.filter(pk=older_run.pk).update(
            created_at=now - timedelta(days=1)
        )
        ForecastRun.objects.filter(pk=latest_run.pk).update(created_at=now)

        response = self.client.get(
            reverse("forecast-accuracy"),
            {"venue": self.venue.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["run_id"], latest_run.id)
        self.assertEqual(response.data["venue"], self.venue.id)
        self.assertEqual(response.data["venue_name"], self.venue.name)
        self.assertAlmostEqual(response.data["accuracy_pct"], 87.5, places=1)
        self.assertAlmostEqual(response.data["mae"], 3.2, places=1)
        self.assertAlmostEqual(response.data["r2_score"], 0.85, places=2)

    def test_12_9_generate_schedule(self):
        ForecastRun.objects.create(
            venue=self.venue,
            status=ForecastRun.Status.COMPLETED,
            make_forecast=True,
        )

        with patch(
            "forecasting.views.generate_schedule_full",
            return_value={
                "schedule_id": 2,
                "year": 2026,
                "month": 4,
                "slots_count": 5,
                "entries_count": 150,
            },
        ):
            response = self.client.post(
                reverse("forecast-generate"),
                {"venue": self.venue.id},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "Расписание создано (черновик).")
        self.assertEqual(response.data["schedule_id"], 2)
        self.assertEqual(response.data["year"], 2026)
        self.assertEqual(response.data["month"], 4)
        self.assertEqual(response.data["slots_count"], 5)
        self.assertEqual(response.data["entries_count"], 150)

    @staticmethod
    def _fake_xlsx():
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            name="real_orders.xlsx",
            content=b"fake-binary-xlsx-content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class ForecastingManagementCommandTests(TestCase):
    """Пункт 12.10: тест management-команды run_forecast."""

    def setUp(self):
        self.venue = Venue.objects.create(
            name="Ресторан Центральный",
            address="ул. Ленина, 1",
            timezone="Europe/Moscow",
        )

    def test_12_10_run_forecast_command(self):
        def fake_execute(runner_self):
            run = runner_self.run
            run.status = ForecastRun.Status.COMPLETED
            run.accuracy_pct = 87.5
            run.mae = 3.2
            run.r2_score = 0.85
            run.finished_at = timezone.now()
            run.save()

        stdout = StringIO()

        with patch(
            "forecasting.management.commands.run_forecast.MLRunner.execute",
            autospec=True,
            side_effect=fake_execute,
        ) as execute_mock, patch(
            "forecasting.management.commands.run_forecast.load_forecast_to_db",
            return_value=24,
        ) as load_mock:
            call_command(
                "run_forecast",
                "--venue",
                str(self.venue.id),
                stdout=stdout,
            )

        run = ForecastRun.objects.latest("id")
        self.assertEqual(run.status, ForecastRun.Status.COMPLETED)
        self.assertEqual(run.venue_id, self.venue.id)
        self.assertTrue(execute_mock.called)
        self.assertTrue(load_mock.called)
        self.assertIn("ForecastRun", stdout.getvalue())
