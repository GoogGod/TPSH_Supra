from django.conf import settings
from django.db import models
from common.mixins import TimestampMixin


class Venue(TimestampMixin):
    """Без изменений — как было."""
    name = models.CharField(max_length=255, verbose_name="Название")
    address = models.CharField(max_length=500, blank=True, default="", verbose_name="Адрес")
    timezone = models.CharField(max_length=63, default="Europe/Moscow", verbose_name="Часовой пояс")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        db_table = "venues"
        verbose_name = "Объект"
        verbose_name_plural = "Объекты"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ═══════════════════ НОВЫЕ МОДЕЛИ ═══════════════════


class MonthlySchedule(TimestampMixin):
    """
    Расписание на месяц для одного заведения.
    Создаётся при загрузке CSV от OR-Tools.
    Проходит путь: draft → published.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"

    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="schedules",
        verbose_name="Объект",
    )
    year = models.PositiveIntegerField(verbose_name="Год")
    month = models.PositiveIntegerField(verbose_name="Месяц")  # 1–12

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Статус",
    )

    raw_csv = models.TextField(
        blank=True,
        default="",
        verbose_name="Исходный CSV",
        help_text="Сохраняем оригинал для отладки и повторного парсинга",
    )

    published_at = models.DateTimeField(null=True, blank=True, verbose_name="Опубликовано в")
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_schedules",
        verbose_name="Опубликовал",
    )

    class Meta:
        db_table = "monthly_schedules"
        verbose_name = "Расписание на месяц"
        verbose_name_plural = "Расписания на месяц"
        unique_together = ("venue", "year", "month")
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.venue.name} — {self.month:02d}/{self.year} [{self.get_status_display()}]"


class WaiterSlot(TimestampMixin):
    """
    Позиция «Официант N» в месячном расписании.
    Сотрудник занимает (claim) или назначается (assign) менеджером.
    Один слот = одна роль на весь месяц (все рабочие дни по паттерну).
    """

    class AssignmentStatus(models.TextChoices):
        OPEN = "open", "Свободно"
        PENDING = "pending", "Ожидает подтверждения"
        CONFIRMED = "confirmed", "Подтверждено"

    schedule = models.ForeignKey(
        MonthlySchedule,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name="Расписание",
    )
    waiter_num = models.PositiveIntegerField(verbose_name="Номер официанта")

    assigned_employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_slots",
        verbose_name="Назначенный сотрудник",
    )
    assignment_status = models.CharField(
        max_length=10,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.OPEN,
        verbose_name="Статус назначения",
    )
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name="Назначен в")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Подтверждён в")

    class Meta:
        db_table = "waiter_slots"
        verbose_name = "Позиция официанта"
        verbose_name_plural = "Позиции официантов"
        unique_together = ("schedule", "waiter_num")
        ordering = ["waiter_num"]

    def __str__(self):
        emp = self.assigned_employee or "свободно"
        return f"Официант {self.waiter_num} — {emp}"


class ScheduleEntry(TimestampMixin):
    """
    Одна строка расписания: один день для одного слота.
    Данные берутся из CSV от OR-Tools.
    """

    class ShiftType(models.TextChoices):
        OFF = "off", "Выходной"
        FULL = "full", "Полная"          # ~09:00–23:00
        MORNING = "morning", "Утренняя"  # ~09:00–17:00
        EVENING = "evening", "Вечерняя"  # ~17:00–01:00

    slot = models.ForeignKey(
        WaiterSlot,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Позиция",
    )
    date = models.DateField(verbose_name="Дата")

    is_working = models.BooleanField(default=False, verbose_name="Рабочий день")
    shift_type = models.CharField(
        max_length=10,
        choices=ShiftType.choices,
        default=ShiftType.OFF,
        verbose_name="Тип смены",
    )
    waiters_needed = models.PositiveIntegerField(
        default=0,
        verbose_name="Требуется официантов",
        help_text="Сколько официантов нужно в этот день (из прогноза)",
    )
    work_start = models.TimeField(null=True, blank=True, verbose_name="Начало")
    work_end = models.TimeField(null=True, blank=True, verbose_name="Конец")
    work_hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        verbose_name="Часы",
    )

    class Meta:
        db_table = "schedule_entries"
        verbose_name = "Запись расписания"
        verbose_name_plural = "Записи расписания"
        unique_together = ("slot", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} — {self.get_shift_type_display()}"