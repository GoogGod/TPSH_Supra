from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient", "notification_type", "title",
        "is_read", "requires_confirmation", "confirmation_status",
        "created_at",
    )
    list_filter = ("notification_type", "is_read", "confirmation_status")
    search_fields = ("title", "message", "recipient__username")
    readonly_fields = ("created_at", "updated_at")