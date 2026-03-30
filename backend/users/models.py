from django.contrib.auth.models import AbstractUser
from django.db import models
from common.mixins import TimestampMixin


class User(AbstractUser, TimestampMixin):

    class Role(models.TextChoices):
        EMPLOYEE_NOOB = "employee_noob", "Сотрудник (стажёр)"
        EMPLOYEE_PRO = "employee_pro", "Сотрудник (опытный)"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"

    class SchedulePattern(models.TextChoices):
        FOUR_THREE = "4/3", "4 через 3"
        FOUR_TWO = "4/2", "4 через 2"
        THREE_TWO = "3/2", "3 через 2"
        TWO_TWO = "2/2", "2 через 2"

    class ShiftDuration(models.TextChoices):
        EIGHT = "8h", "8 часов"
        FOURTEEN = "14h", "14 часов"
        CUSTOM = "custom", "По договорённости"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE_NOOB,    # ← новый default
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

    phone = models.CharField(max_length=20, blank=True, default="", verbose_name="Телефон")

    schedule_pattern = models.CharField(
        max_length=10,
        choices=SchedulePattern.choices,
        default=SchedulePattern.FOUR_TWO,
        verbose_name="График работы",
    )

    shift_duration = models.CharField(
        max_length=10,
        choices=ShiftDuration.choices,
        default=ShiftDuration.FOURTEEN,
        verbose_name="Продолжительность смены",
        help_text="Определяет допустимые типы смен для сотрудника",
    )

    first_name = models.CharField(max_length=150, verbose_name="Имя")
    last_name = models.CharField(max_length=150, verbose_name="Фамилия")
    email = models.EmailField(unique=True, verbose_name="Email")

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    # ── Роль ──

    @property
    def is_employee(self) -> bool:
        """Любой сотрудник (noob или pro)."""
        return self.role in (self.Role.EMPLOYEE_NOOB, self.Role.EMPLOYEE_PRO)

    @property
    def is_noob(self) -> bool:
        return self.role == self.Role.EMPLOYEE_NOOB

    @property
    def is_pro(self) -> bool:
        return self.role == self.Role.EMPLOYEE_PRO

    @property
    def is_manager(self) -> bool:
        return self.role == self.Role.MANAGER

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    # ── График ──

    @property
    def work_days(self) -> int:
        return int(self.schedule_pattern.split("/")[0])

    @property
    def off_days(self) -> int:
        return int(self.schedule_pattern.split("/")[1])

    @property
    def cycle_length(self) -> int:
        return self.work_days + self.off_days