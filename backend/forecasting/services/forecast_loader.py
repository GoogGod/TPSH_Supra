"""
Загрузка результатов прогноза из CSV в БД.
Вызывается после успешного завершения ML-пайплайна.
"""

import csv
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction

from forecasting.models import ForecastRun, HourlyForecast


class ForecastLoadError(Exception):
    pass


def load_forecast_to_db(forecast_run: ForecastRun, csv_path: Path = None):
    """
    Прочитать forecast.csv и загрузить в HourlyForecast.
    Привязать к forecast_run и его venue.
    """
    if csv_path is None:
        csv_path = settings.ML_DATA_PREDICTED / "forecast.csv"
    else:
        csv_path = Path(csv_path)

    if not csv_path.exists():
        raise ForecastLoadError(f"Файл прогноза не найден: {csv_path}")

    rows = _read_forecast_csv(csv_path)
    if not rows:
        raise ForecastLoadError("forecast.csv пуст")

    with transaction.atomic():
        HourlyForecast.objects.filter(run=forecast_run).delete()

        forecasts = [
            HourlyForecast(
                run=forecast_run,
                venue=forecast_run.venue,
                forecast_datetime=row["forecast_datetime"],
                date=row["date"],
                hour=row["hour"],
                day_of_week=row["day_of_week"],
                is_peak_hour=row["is_peak_hour"],
                is_weekend=row["is_weekend"],
                is_holiday=row["is_holiday"],
                orders_predicted=row["orders_predicted"],
                orders_with_buffer=row["orders_with_buffer"],
                guests_predicted=row["guests_predicted"],
                guests_with_buffer=row["guests_with_buffer"],
            )
            for row in rows
        ]

        HourlyForecast.objects.bulk_create(forecasts)

    return len(forecasts)


def _read_forecast_csv(csv_path: Path):
    """Парсинг forecast.csv (поддержка старого и нового форматов)."""
    rows = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        sample = f.read(1024)
        f.seek(0)
        delimiter = "\t" if "\t" in sample.split("\n")[0] else ","

        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            try:
                rows.append(_parse_forecast_row(row))
            except Exception as exc:
                print(f"Forecast CSV: пропущена строка — {exc}")

    return rows


def _parse_forecast_row(row):
    """Распарсить одну строку forecast.csv."""
    # Старый формат: forecast_datetime
    # Новый формат: datetime
    dt_str = (
        str(row.get("forecast_datetime") or "").strip()
        or str(row.get("datetime") or "").strip()
    )
    if not dt_str:
        raise ValueError("Отсутствует forecast_datetime/datetime")

    try:
        forecast_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        forecast_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

    date_str = str(row.get("date") or "").strip()
    if date_str:
        try:
            date_value = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            date_value = forecast_dt.date()
    else:
        date_value = forecast_dt.date()

    hour_raw = row.get("hour")
    hour_value = int(hour_raw) if str(hour_raw).strip() else forecast_dt.hour

    dow_raw = row.get("day_of_week")
    dow_value = int(dow_raw) if str(dow_raw).strip() else forecast_dt.weekday()

    def as_bool(value, default=False):
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "y"):
            return True
        if text in ("0", "false", "no", "n"):
            return False
        return default

    def as_float(value, default=0.0):
        if value is None or str(value).strip() == "":
            return default
        return float(value)

    return {
        "forecast_datetime": forecast_dt,
        "date": date_value,
        "hour": hour_value,
        "day_of_week": dow_value,
        "is_peak_hour": as_bool(row.get("is_peak_hour"), default=False),
        "is_weekend": as_bool(row.get("is_weekend"), default=False),
        "is_holiday": as_bool(row.get("is_holiday"), default=False),
        "orders_predicted": as_float(row.get("orders_predicted"), default=0.0),
        "orders_with_buffer": as_float(row.get("orders_with_buffer"), default=0.0),
        "guests_predicted": as_float(row.get("guests_predicted"), default=0.0),
        "guests_with_buffer": as_float(row.get("guests_with_buffer"), default=0.0),
    }
