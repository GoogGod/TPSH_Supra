import csv
import io
from datetime import datetime

from django.db import transaction

from shifts.models import MonthlySchedule, WaiterSlot, ScheduleEntry


SHIFT_PATTERN_MAP = {
    "Выходной": "off",
    "Полная": "full",
    "Утренняя": "morning",
    "Вечерняя": "evening",
    "Смена": "full",
    "off": "off",
    "full": "full",
    "morning": "morning",
    "evening": "evening",
    "shift": "full",
}

# Маппинг колонок от разных версий scheduler -> единый формат parser.
COLUMN_ALIASES = {
    "forecast_date": "date",
    "waiter_id": "waiter_id",
    "waiter_number": "waiter_num",
    "waiter_num": "waiter_num",
    "working": "is_working",
    "shift_type_code": "is_working",
    "pattern": "shift_pattern",
    "shift_type": "shift_pattern",
    "needed": "waiters_needed",
    "start": "work_start",
    "end": "work_end",
    "hours": "work_hours",
}


class CSVParseError(Exception):
    """Ошибка при разборе CSV."""


def normalize_column_names(row: dict) -> dict:
    """Привести имена колонок к стандартному формату."""
    normalized = {}
    for key, value in row.items():
        clean_key = str(key).strip().lower()
        mapped_key = COLUMN_ALIASES.get(clean_key, clean_key)
        normalized[mapped_key] = value
    return normalized


def parse_schedule_csv(csv_file, venue):
    """
    Разобрать CSV расписания, создать MonthlySchedule + WaiterSlots + ScheduleEntries.

    Ожидаемые колонки:
        date, waiter_num, is_working, shift_pattern, waiters_needed, work_start, work_end, work_hours

    Допускаются alias-колонки из scheduler.py.
    """
    try:
        if hasattr(csv_file, "read"):
            raw = csv_file.read()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8-sig")
        else:
            raw = csv_file
    except Exception as exc:
        raise CSVParseError(f"Не удалось прочитать файл: {exc}")

    raw = str(raw).strip()
    if not raw:
        raise CSVParseError("CSV файл пуст")

    delimiter = "\t" if "\t" in raw.split("\n")[0] else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)

    rows = []
    for i, row in enumerate(reader, start=2):
        try:
            row = normalize_column_names(row)
            rows.append(_parse_row(row))
        except Exception as exc:
            raise CSVParseError(f"Ошибка в строке {i}: {exc}")

    if not rows:
        raise CSVParseError("CSV не содержит данных")

    first_date = rows[0]["date"]
    year = first_date.year
    month = first_date.month

    with transaction.atomic():
        MonthlySchedule.objects.filter(
            venue=venue,
            year=year,
            month=month,
            status="draft",
        ).delete()

        if MonthlySchedule.objects.filter(
            venue=venue,
            year=year,
            month=month,
            status="published",
        ).exists():
            raise CSVParseError(
                f"Расписание на {month:02d}/{year} уже опубликовано. "
                "Удалите или архивируйте перед загрузкой нового."
            )

        schedule = MonthlySchedule.objects.create(
            venue=venue,
            year=year,
            month=month,
            status="draft",
            raw_csv=raw,
        )

        waiter_nums = sorted(set(r["waiter_num"] for r in rows))
        slots = {}
        for num in waiter_nums:
            slot = WaiterSlot.objects.create(
                schedule=schedule,
                waiter_num=num,
            )
            slots[num] = slot

        entries = [
            ScheduleEntry(
                slot=slots[r["waiter_num"]],
                date=r["date"],
                is_working=r["is_working"],
                shift_type=r["shift_type"],
                waiters_needed=r["waiters_needed"],
                work_start=r["work_start"],
                work_end=r["work_end"],
                work_hours=r["work_hours"],
            )
            for r in rows
        ]
        ScheduleEntry.objects.bulk_create(entries)

    return schedule


def _parse_row(row):
    date = _parse_date(row.get("date", ""))

    waiter_num = int(float(row.get("waiter_num", 0) or 0))

    shift_pattern_raw = str(row.get("shift_pattern", "") or "").strip()
    shift_type = _normalize_shift_pattern(shift_pattern_raw)

    work_hours = float(row.get("work_hours", 0) or 0)
    is_working_raw = row.get("is_working", "")
    if str(is_working_raw).strip() == "":
        is_working = shift_type != "off" or work_hours > 0
    else:
        is_working = _parse_bool(is_working_raw)

    waiters_needed = int(float(row.get("waiters_needed", 0) or 0))

    work_start = _parse_time(row.get("work_start", ""))
    work_end = _parse_time(row.get("work_end", ""))

    return {
        "date": date,
        "waiter_num": waiter_num,
        "is_working": is_working,
        "shift_type": shift_type,
        "waiters_needed": waiters_needed,
        "work_start": work_start,
        "work_end": work_end,
        "work_hours": work_hours,
    }


def _parse_date(value: str):
    value = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Некорректная дата: {value}")


def _parse_time(value):
    value = str(value or "").strip()
    if not value:
        return None

    # Поддержка формата "10" / "10.0" из scheduler.
    try:
        if value.replace(".", "", 1).isdigit():
            hour = int(float(value)) % 24
            return datetime.strptime(f"{hour:02d}:00", "%H:%M").time()
    except ValueError:
        pass

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue

    return None


def _normalize_shift_pattern(value: str) -> str:
    if value in SHIFT_PATTERN_MAP:
        return SHIFT_PATTERN_MAP[value]

    lowered = value.lower()
    if lowered in SHIFT_PATTERN_MAP:
        return SHIFT_PATTERN_MAP[lowered]

    # Fallback по ключевым словам
    if "morning" in lowered or "утрен" in lowered:
        return "morning"
    if "evening" in lowered or "вечер" in lowered:
        return "evening"
    if "full" in lowered or "смен" in lowered or "полн" in lowered:
        return "full"
    if "off" in lowered or "выход" in lowered:
        return "off"

    return "off"


def _parse_bool(value):
    value_str = str(value).strip().lower()
    if value_str in {"1", "true", "yes", "y"}:
        return True
    if value_str in {"0", "false", "no", "n", ""}:
        return False

    try:
        return bool(int(float(value_str)))
    except (ValueError, TypeError):
        return False
