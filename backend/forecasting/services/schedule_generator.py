"""
Schedule generation adapter for ml_data.

Flow:
1. Run ml_data scheduler -> waiter_schedule.csv
2. Parse CSV into MonthlySchedule + slots + entries
"""

import os
import traceback
from pathlib import Path

import pandas as pd
from django.conf import settings

from shifts.services.csv_parser import CSVParseError, parse_schedule_csv


class ScheduleGenerationError(Exception):
    pass


def _import_scheduler_algorithm():
    """Import scheduler entrypoint from new/legacy ml_data layouts."""
    try:
        from ml_data.scheduler_algorithm import create_waiter_schedule_algorithm

        return create_waiter_schedule_algorithm
    except Exception:
        # Compatibility for local runs when ml_data is resolved via cwd.
        from scheduler_algorithm import create_waiter_schedule_algorithm

        return create_waiter_schedule_algorithm


def run_scheduler():
    """
    Invoke ml_data scheduler to generate waiter_schedule.csv from forecast.csv.
    """
    original_cwd = os.getcwd()

    try:
        os.chdir(settings.ML_DATA_DIR)

        forecast_path = Path(settings.ML_DATA_PREDICTED) / "forecast.csv"
        output_path = Path(settings.ML_DATA_PREDICTED) / "waiter_schedule.csv"

        if not forecast_path.exists():
            raise ScheduleGenerationError(f"Forecast file not found: {forecast_path}")

        create_waiter_schedule_algorithm = _import_scheduler_algorithm()

        forecast_df = pd.read_csv(forecast_path)
        if forecast_df.empty:
            raise ScheduleGenerationError("forecast.csv is empty")

        create_waiter_schedule_algorithm(
            forecast_df=forecast_df,
            output_path=str(output_path),
            verbose=False,
        )

    except Exception as e:
        raise ScheduleGenerationError(
            f"Scheduler error: {type(e).__name__}: {e}\n{traceback.format_exc()}"
        )
    finally:
        os.chdir(original_cwd)


def load_generated_schedule(venue):
    """
    Read waiter_schedule.csv and create MonthlySchedule via existing parser.
    """
    csv_path = Path(settings.ML_DATA_PREDICTED) / "waiter_schedule.csv"

    if not csv_path.exists():
        raise ScheduleGenerationError(
            f"Schedule file not found: {csv_path}. Ensure scheduler completed successfully."
        )

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            csv_content = f.read()

        return parse_schedule_csv(csv_content, venue)

    except CSVParseError as e:
        raise ScheduleGenerationError(f"Schedule CSV parse error: {e}")


def generate_schedule_full(venue, forecast_run=None):
    """
    Full cycle: scheduler -> CSV parse -> MonthlySchedule.
    """
    run_scheduler()
    schedule = load_generated_schedule(venue)

    return {
        "schedule_id": schedule.id,
        "year": schedule.year,
        "month": schedule.month,
        "slots_count": schedule.slots.count(),
        "entries_count": sum(slot.entries.count() for slot in schedule.slots.all()),
    }
