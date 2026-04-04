from django.contrib.auth.models import AbstractUser
from django.db import models
from common.mixins import TimestampMixin


class User(AbstractUser, TimestampMixin):

    class Role(models.TextChoices):
        EMPLOYEE_NOOB = "employee_noob", "Сотрудник (стажёр)"
        EMPLOYEE_PRO = "employee_pro", "Сотрудник (опытный)"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE_NOOB,
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

    @property
    def is_employee(self) -> bool:
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
