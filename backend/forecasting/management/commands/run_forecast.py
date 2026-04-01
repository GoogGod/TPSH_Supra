from django.core.management.base import BaseCommand, CommandError

from shifts.models import Venue
from forecasting.models import ForecastRun
from forecasting.services.ml_runner import MLRunner
from forecasting.services.forecast_loader import load_forecast_to_db


class Command(BaseCommand):
    help = "Запустить ML-пайплайн: обработка данных → обучение → прогноз"

    def add_arguments(self, parser):
        parser.add_argument(
            "--venue", type=int, required=True,
            help="ID объекта",
        )
        parser.add_argument(
            "--no-process", action="store_true",
            help="Пропустить обработку данных",
        )
        parser.add_argument(
            "--no-train", action="store_true",
            help="Пропустить обучение",
        )
        parser.add_argument(
            "--no-forecast", action="store_true",
            help="Пропустить прогноз",
        )
        parser.add_argument(
            "--from-date", type=str, default=None,
            help="Начало прогноза (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--to-date", type=str, default=None,
            help="Конец прогноза (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--hours", type=int, default=720,
            help="Часов вперёд (по умолчанию 720 = 30 дней)",
        )

    def handle(self, *args, **options):
        try:
            venue = Venue.objects.get(id=options["venue"])
        except Venue.DoesNotExist:
            raise CommandError(f"Venue #{options['venue']} не найден")

        self.stdout.write(f"Venue: {venue.name}")

        from datetime import datetime

        run = ForecastRun.objects.create(
            venue=venue,
            process_data=not options["no_process"],
            train_model=not options["no_train"],
            make_forecast=not options["no_forecast"],
            evaluate=not options["no_train"],
            forecast_from=(
                datetime.strptime(options["from_date"], "%Y-%m-%d").date()
                if options["from_date"] else None
            ),
            forecast_to=(
                datetime.strptime(options["to_date"], "%Y-%m-%d").date()
                if options["to_date"] else None
            ),
            hours_ahead=options["hours"],
        )

        self.stdout.write(f"ForecastRun #{run.pk} создан")

        runner = MLRunner(run)

        try:
            runner.execute()
            self.stdout.write(self.style.SUCCESS(
                f"Пайплайн завершён. Статус: {run.status}"
            ))

            if run.accuracy_pct:
                self.stdout.write(f"  Точность: {run.accuracy_pct}%")
            if run.mae:
                self.stdout.write(f"  MAE: {run.mae}")
            if run.r2_score:
                self.stdout.write(f"  R²: {run.r2_score}")

            # Загрузить прогнозы в БД
            if run.make_forecast and not options["no_forecast"]:
                count = load_forecast_to_db(run)
                self.stdout.write(f"  Загружено прогнозов: {count}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Ошибка: {e}"
            ))
            self.stdout.write(run.error_message)