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
}


class CSVParseError(Exception):
    """Ошибка при разборе CSV."""
    pass


def parse_schedule_csv(csv_file, venue):
    """
    Разобрать CSV от OR-Tools, создать MonthlySchedule + WaiterSlots + ScheduleEntries.

    Формат CSV (tab-separated):
        date  waiter_id  waiter_num  is_working  shift_pattern  waiters_needed  work_start  work_end  work_hours

    Возвращает созданный MonthlySchedule.
    Выбрасывает CSVParseError при ошибках.
    """
    try:
        if hasattr(csv_file, "read"):
            raw = csv_file.read()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8-sig")  # utf-8-sig убирает BOM
        else:
            raw = csv_file
    except Exception as e:
        raise CSVParseError(f"Не удалось прочитать файл: {e}")

    raw = raw.strip()
    if not raw:
        raise CSVParseError("CSV файл пуст")

    # Определяем разделитель
    delimiter = "\t" if "\t" in raw.split("\n")[0] else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)

    rows = []
    for i, row in enumerate(reader, start=2):
        try:
            rows.append(_parse_row(row))
        except Exception as e:
            raise CSVParseError(f"Ошибка в строке {i}: {e}")

    if not rows:
        raise CSVParseError("CSV не содержит данных")

    # Определяем год и месяц по первой дате
    first_date = rows[0]["date"]
    year = first_date.year
    month = first_date.month

    with transaction.atomic():
        # Удалить черновик если уже есть
        MonthlySchedule.objects.filter(
            venue=venue, year=year, month=month, status="draft"
        ).delete()

        # Проверить что опубликованного нет
        if MonthlySchedule.objects.filter(
            venue=venue, year=year, month=month, status="published"
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

        # Создать слоты
        waiter_nums = sorted(set(r["waiter_num"] for r in rows))
        slots = {}
        for num in waiter_nums:
            slot = WaiterSlot.objects.create(
                schedule=schedule,
                waiter_num=num,
            )
            slots[num] = slot

        # Создать записи
        entries = []
        for r in rows:
            entries.append(ScheduleEntry(
                slot=slots[r["waiter_num"]],
                date=r["date"],
                is_working=r["is_working"],
                shift_type=r["shift_type"],
                waiters_needed=r["waiters_needed"],
                work_start=r["work_start"],
                work_end=r["work_end"],
                work_hours=r["work_hours"],
            ))

        ScheduleEntry.objects.bulk_create(entries)

    return schedule


def _parse_row(row):
    """Распарсить одну строку CSV в словарь с типизированными значениями."""
    # Дата: DD/MM/YYYY или D/MM/YYYY
    date_str = row.get("date", "").strip()
    try:
        date = datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()

    waiter_num = int(row.get("waiter_num", 0))
    is_working = bool(int(row.get("is_working", 0)))

    shift_pattern = row.get("shift_pattern", "").strip()
    shift_type = SHIFT_PATTERN_MAP.get(shift_pattern, "off")

    waiters_needed = int(row.get("waiters_needed", 0) or 0)

    work_start = _parse_time(row.get("work_start", ""))
    work_end = _parse_time(row.get("work_end", ""))
    work_hours = float(row.get("work_hours", 0) or 0)

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


def _parse_time(value):
    """Распарсить время из строки. Вернуть None если пусто."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None