from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username", "last_name", "first_name",
        "role", "venue", "schedule_pattern", "shift_duration",
        "is_active",
    )
    list_filter = ("role", "venue", "schedule_pattern", "shift_duration", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("last_name", "first_name")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Supra — роль и объект", {
            "fields": ("role", "venue", "phone"),
        }),
        ("Supra — график", {
            "fields": ("schedule_pattern", "shift_duration"),
            "description": "Определяет как scheduler формирует расписание для сотрудника.",
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Supra", {
            "fields": (
                "first_name", "last_name", "email",
                "role", "venue", "phone",
                "schedule_pattern", "shift_duration",
            ),
        }),
    )