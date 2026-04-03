import sys
import types
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from forecasting.models import ForecastRun
from forecasting.services.ml_runner import MLRunner
from shifts.models import Venue


class MLRunnerDateRangeTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(
            name="Ресторан Центральный",
            address="ул. Ленина, 1",
            timezone="Europe/Moscow",
        )

    def test_execute_passes_to_date_as_end_of_day(self):
        run = ForecastRun.objects.create(
            venue=self.venue,
            process_data=False,
            train_model=False,
            make_forecast=True,
            evaluate=False,
            forecast_from=date(2026, 4, 1),
            forecast_to=date(2026, 4, 30),
        )

        captured_kwargs = {}

        fake_main_module = types.ModuleType("ml_data.main")
        fake_main_module.DATA_PRED_DIR = "."

        def fake_main(**kwargs):
            captured_kwargs.update(kwargs)
            return {}

        fake_main_module.main = fake_main

        fake_ml_data_package = types.ModuleType("ml_data")
        fake_ml_data_package.main = fake_main_module

        with patch.dict(
            sys.modules,
            {
                "ml_data": fake_ml_data_package,
                "ml_data.main": fake_main_module,
            },
        ):
            runner = MLRunner(run)
            runner.execute(make_schedule=False)

        run.refresh_from_db()
        self.assertEqual(run.status, ForecastRun.Status.COMPLETED)
        self.assertEqual(captured_kwargs["from_date"], "2026-04-01")
        self.assertEqual(captured_kwargs["to_date"], "2026-04-30 23:59:59")
