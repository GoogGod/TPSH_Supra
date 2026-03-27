from django.contrib.auth.models import AbstractUser
from django.db import models
from common.mixins import TimestampMixin


class User(AbstractUser, TimestampMixin):
    """
    Пользователь системы Supra.

    Роли: employee (официант), manager, admin.
    Привязан к объекту (venue).

    Поля schedule_pattern и shift_duration определяют
    как scheduler формирует расписание для сотрудника.
    Назначаются менеджером при создании/редактировании.
    """

    # ────────────── Choices ──────────────

    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Сотрудник"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"

    class SchedulePattern(models.TextChoices):
        """
        Паттерн рабочих/выходных дней.
        Первое число — рабочие дни подряд,
        второе — выходные дни подряд.
        """
        FOUR_THREE = "4/3", "4 через 3"
        FOUR_TWO = "4/2", "4 через 2"
        THREE_TWO = "3/2", "3 через 2"
        TWO_TWO = "2/2", "2 через 2"

    class ShiftDuration(models.TextChoices):
        """
        Продолжительность рабочего дня.
        Определяет допустимые типы смен:
          8h  → вечерняя (17:00–01:00)
          14h → полная (09:00–23:00 или 11:00–01:00)
          custom → scheduler назначает любую
        """
        EIGHT = "8h", "8 часов (вечерняя)"
        FOURTEEN = "14h", "14 часов (полная)"
        CUSTOM = "custom", "По договорённости"

    # ────────────── Поля ──────────────

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        verbose_name="Роль",
        db_index=True,
    )

    venue = models.ForeignKey(
        "shifts.Venue",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
        verbose_name="Объект",
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Телефон",
    )

    schedule_pattern = models.CharField(
        max_length=10,
        choices=SchedulePattern.choices,
        default=SchedulePattern.FOUR_TWO,
        verbose_name="График работы",
        help_text="Чередование рабочих и выходных дней",
    )

    shift_duration = models.CharField(
        max_length=10,
        choices=ShiftDuration.choices,
        default=ShiftDuration.FOURTEEN,
        verbose_name="Продолжительность смены",
        help_text="Определяет допустимые типы смен для сотрудника",
    )

    # Переопределяем для verbose
    first_name = models.CharField(max_length=150, verbose_name="Имя")
    last_name = models.CharField(max_length=150, verbose_name="Фамилия")
    email = models.EmailField(unique=True, verbose_name="Email")

    # ────────────── Meta ──────────────

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    # ────────────── Свойства роли ──────────────

    @property
    def is_employee(self) -> bool:
        return self.role == self.Role.EMPLOYEE

    @property
    def is_manager(self) -> bool:
        return self.role == self.Role.MANAGER

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    # ────────────── Свойства графика ──────────────

    @property
    def work_days(self) -> int:
        """Кол-во рабочих дней подряд в паттерне."""
        return int(self.schedule_pattern.split("/")[0])

    @property
    def off_days(self) -> int:
        """Кол-во выходных дней подряд в паттерне."""
        return int(self.schedule_pattern.split("/")[1])

    @property
    def cycle_length(self) -> int:
        """Длина полного цикла (рабочие + выходные)."""
        return self.work_days + self.off_days