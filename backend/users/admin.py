from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "last_name",
        "first_name",
        "role",
        "venue",
        "is_active",
    )
    list_filter = ("role", "venue", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("last_name", "first_name")

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Supra — роль и объект",
            {
                "fields": (
                    "role",
                    "venue",
                    "phone",
                )
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Supra",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "role",
                    "venue",
                    "phone",
                )
            },
        ),
    )

    actions = ["make_pro", "make_noob"]

    @admin.action(description="Повысить до опытного (pro)")
    def make_pro(self, request, queryset):
        updated = queryset.filter(role="employee_noob").update(role="employee_pro")
        self.message_user(request, f"Повышено: {updated}")

    @admin.action(description="Понизить до стажёра (noob)")
    def make_noob(self, request, queryset):
        updated = queryset.filter(role="employee_pro").update(role="employee_noob")
        self.message_user(request, f"Понижено: {updated}")
