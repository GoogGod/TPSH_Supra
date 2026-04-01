"""
Генерация расписания:
1. Вызвать scheduler.py из ml_data → получить waiter_schedule.csv
2. Прочитать CSV и создать MonthlySchedule + WaiterSlots + ScheduleEntries
"""

import os
import traceback

from django.conf import settings
from django.utils import timezone

from shifts.services.csv_parser import parse_schedule_csv, CSVParseError


class ScheduleGenerationError(Exception):
    pass


def run_scheduler():
    """
    Вызвать ml_data/scheduler.py для генерации waiter_schedule.csv.
    Scheduler читает data/predicted/forecast.csv и создаёт расписание.
    """
    original_cwd = os.getcwd()

    try:
        os.chdir(settings.ML_DATA_DIR)

        from ml_data import scheduler as scheduler_module

        forecast_path = str(settings.ML_DATA_PREDICTED / "forecast.csv")
        output_path = str(settings.ML_DATA_PREDICTED / "waiter_schedule.csv")

        if hasattr(scheduler_module, "main") and callable(scheduler_module.main):
            scheduler_module.main(
                forecast_path=forecast_path,
                output_path=output_path,
                verbose=False,
            )
        elif hasattr(scheduler_module, "create_waiter_schedule") and callable(
            scheduler_module.create_waiter_schedule
        ):
            scheduler_module.create_waiter_schedule(
                forecast_path=forecast_path,
                output_path=output_path,
                verbose=False,
            )
        else:
            raise ScheduleGenerationError(
                "scheduler.py не содержит ни main(), ни create_waiter_schedule()."
            )

    except Exception as e:
        raise ScheduleGenerationError(
            f"Ошибка scheduler.py: {type(e).__name__}: {e}\n{traceback.format_exc()}"
        )
    finally:
        os.chdir(original_cwd)


def load_generated_schedule(venue):
    """
    Прочитать waiter_schedule.csv и создать MonthlySchedule.
    Использует существующий csv_parser из shifts.

    Возвращает MonthlySchedule (draft).
    """
    csv_path = settings.ML_DATA_PREDICTED / "waiter_schedule.csv"

    if not csv_path.exists():
        raise ScheduleGenerationError(
            f"Файл расписания не найден: {csv_path}. "
            "Убедитесь что scheduler.py отработал."
        )

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            csv_content = f.read()

        schedule = parse_schedule_csv(csv_content, venue)
        return schedule

    except CSVParseError as e:
        raise ScheduleGenerationError(f"Ошибка парсинга расписания: {e}")


def generate_schedule_full(venue, forecast_run=None):
    """
    Полный цикл: scheduler.py → чтение CSV → MonthlySchedule.

    Возвращает dict с результатами.
    """
    # Шаг 1: запустить scheduler
    run_scheduler()

    # Шаг 2: загрузить в MonthlySchedule
    schedule = load_generated_schedule(venue)

    return {
        "schedule_id": schedule.id,
        "year": schedule.year,
        "month": schedule.month,
        "slots_count": schedule.slots.count(),
        "entries_count": sum(
            slot.entries.count() for slot in schedule.slots.all()
        ),
    }
