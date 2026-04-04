from rest_framework import serializers

from .models import MonthlySchedule, ScheduleEntry, Venue, WaiterSlot


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "address", "timezone", "is_active"]
        read_only_fields = fields


class VenueWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["name", "address", "timezone", "is_active"]


class ScheduleEntrySerializer(serializers.ModelSerializer):
    shift_type_display = serializers.CharField(
        source="get_shift_type_display",
        read_only=True,
    )

    class Meta:
        model = ScheduleEntry
        fields = [
            "id",
            "date",
            "is_working",
            "shift_type",
            "shift_type_display",
            "waiters_needed",
            "work_start",
            "work_end",
            "work_hours",
        ]
        read_only_fields = fields


class ScheduleEntryPatchSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = ScheduleEntry
        fields = [
            "id",
            "is_working",
            "shift_type",
            "waiters_needed",
            "work_start",
            "work_end",
            "work_hours",
        ]
        extra_kwargs = {
            "is_working": {"required": False},
            "shift_type": {"required": False},
            "waiters_needed": {"required": False},
            "work_start": {"required": False, "allow_null": True},
            "work_end": {"required": False, "allow_null": True},
            "work_hours": {"required": False},
        }

    def validate(self, attrs):
        if self.instance is not None and set(attrs.keys()) == {"id"}:
            raise serializers.ValidationError(
                "Передайте хотя бы одно поле для изменения.",
            )
        return attrs

    def to_internal_value(self, data):
        if isinstance(data, dict):
            normalized = data.copy()
            for field in ("work_start", "work_end"):
                if normalized.get(field) == "":
                    normalized[field] = None
            data = normalized
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        # id нужен только для маппинга в bulk update.
        validated_data.pop("id", None)
        return super().update(instance, validated_data)


class WaiterSlotSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_role = serializers.SerializerMethodField()
    employee_role_display = serializers.SerializerMethodField()
    employee_pro = serializers.SerializerMethodField()
    employee_noob = serializers.SerializerMethodField()
    assignment_status_display = serializers.CharField(
        source="get_assignment_status_display",
        read_only=True,
    )

    class Meta:
        model = WaiterSlot
        fields = [
            "id",
            "waiter_num",
            "assigned_employee",
            "employee_name",
            "employee_role",
            "employee_role_display",
            "employee_pro",
            "employee_noob",
            "assignment_status",
            "assignment_status_display",
            "assigned_at",
            "confirmed_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        if obj.assigned_employee:
            return obj.assigned_employee.get_full_name() or obj.assigned_employee.username
        return None

    def get_employee_role(self, obj):
        return obj.employee_level

    def get_employee_role_display(self, obj):
        if obj.employee_level:
            return obj.get_employee_level_display()
        return None

    def get_employee_pro(self, obj):
        return obj.employee_level == "employee_pro"

    def get_employee_noob(self, obj):
        return obj.employee_level == "employee_noob"


class WaiterSlotDetailSerializer(WaiterSlotSerializer):
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
            "id",
            "venue",
            "venue_name",
            "year",
            "month",
            "status",
            "status_display",
            "total_slots",
            "filled_slots",
            "published_at",
            "created_at",
        ]
        read_only_fields = fields


class MonthlyScheduleDetailSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    slots = WaiterSlotDetailSerializer(many=True, read_only=True)

    class Meta:
        model = MonthlySchedule
        fields = [
            "id",
            "venue",
            "venue_name",
            "year",
            "month",
            "status",
            "status_display",
            "published_at",
            "created_at",
            "slots",
        ]
        read_only_fields = fields
