from rest_framework import serializers
from .models import Venue, MonthlySchedule, WaiterSlot, ScheduleEntry


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "address", "timezone", "is_active"]
        read_only_fields = fields


class ScheduleEntrySerializer(serializers.ModelSerializer):
    shift_type_display = serializers.CharField(
        source="get_shift_type_display", read_only=True
    )

    class Meta:
        model = ScheduleEntry
        fields = [
            "id", "date", "is_working",
            "shift_type", "shift_type_display",
            "waiters_needed",
            "work_start", "work_end", "work_hours",
        ]
        read_only_fields = fields


class WaiterSlotSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    assignment_status_display = serializers.CharField(
        source="get_assignment_status_display", read_only=True
    )

    class Meta:
        model = WaiterSlot
        fields = [
            "id", "waiter_num",
            "assigned_employee", "employee_name",
            "assignment_status", "assignment_status_display",
            "assigned_at", "confirmed_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        if obj.assigned_employee:
            return obj.assigned_employee.get_full_name() or obj.assigned_employee.username
        return None


class WaiterSlotDetailSerializer(WaiterSlotSerializer):
    """Слот + все дни."""
    entries = ScheduleEntrySerializer(many=True, read_only=True)

    class Meta(WaiterSlotSerializer.Meta):
        fields = WaiterSlotSerializer.Meta.fields + ["entries"]


class MonthlyScheduleListSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_slots = serializers.IntegerField(read_only=True)
    filled_slots = serializers.IntegerField(read_only=True)

    class Meta:
        model = MonthlySchedule
        fields = [
            "id", "venue", "venue_name",
            "year", "month",
            "status", "status_display",
            "total_slots", "filled_slots",
            "published_at", "created_at",
        ]
        read_only_fields = fields


class MonthlyScheduleDetailSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    slots = WaiterSlotDetailSerializer(many=True, read_only=True)

    class Meta:
        model = MonthlySchedule
        fields = [
            "id", "venue", "venue_name",
            "year", "month",
            "status", "status_display",
            "published_at", "created_at",
            "slots",
        ]
        read_only_fields = fields