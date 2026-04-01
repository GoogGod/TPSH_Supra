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


def load_forecast_to_db(forecast_run: ForecastRun):
    """
    Прочитать data/predicted/forecast.csv и загрузить в HourlyForecast.
    Привязать к forecast_run и его venue.
    """
    csv_path = settings.ML_DATA_PREDICTED / "forecast.csv"

    if not csv_path.exists():
        raise ForecastLoadError(
            f"Файл прогноза не найден: {csv_path}"
        )

    rows = _read_forecast_csv(csv_path)

    if not rows:
        raise ForecastLoadError("forecast.csv пуст")

    with transaction.atomic():
        # Удалить старые прогнозы этого run
        HourlyForecast.objects.filter(run=forecast_run).delete()

        forecasts = []
        for row in rows:
            forecasts.append(HourlyForecast(
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
            ))

        HourlyForecast.objects.bulk_create(forecasts)

    return len(forecasts)


def _read_forecast_csv(csv_path: Path):
    """Парсинг forecast.csv."""
    rows = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        # Определить разделитель
        sample = f.read(1024)
        f.seek(0)
        delimiter = "\t" if "\t" in sample.split("\n")[0] else ","

        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            try:
                rows.append(_parse_forecast_row(row))
            except Exception as e:
                # Пропускаем битые строки, логируем
                print(f"Forecast CSV: пропущена строка — {e}")

    return rows


def _parse_forecast_row(row):
    """Распарсить одну строку forecast.csv."""
    dt_str = row.get("forecast_datetime", "").strip()
    try:
        forecast_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        forecast_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

    date_str = row.get("date", "").strip()
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        date = forecast_dt.date()

    return {
        "forecast_datetime": forecast_dt,
        "date": date,
        "hour": int(row.get("hour", 0)),
        "day_of_week": int(row.get("day_of_week", 0)),
        "is_peak_hour": bool(int(row.get("is_peak_hour", 0))),
        "is_weekend": bool(int(row.get("is_weekend", 0))),
        "is_holiday": bool(int(row.get("is_holiday", 0))),
        "orders_predicted": float(row.get("orders_predicted", 0)),
        "orders_with_buffer": float(row.get("orders_with_buffer", 0)),
        "guests_predicted": float(row.get("guests_predicted", 0)),
        "guests_with_buffer": float(row.get("guests_with_buffer", 0)),
    }