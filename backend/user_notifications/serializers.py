from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(
        source="get_notification_type_display", read_only=True
    )
    confirmation_status_display = serializers.CharField(
        source="get_confirmation_status_display", read_only=True
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type", "type_display",
            "title", "message",
            "is_read",
            "requires_confirmation",
            "confirmation_status", "confirmation_status_display",
            "confirmed_at",
            "related_schedule", "related_slot",
            "created_at",
        ]
        read_only_fields = fields