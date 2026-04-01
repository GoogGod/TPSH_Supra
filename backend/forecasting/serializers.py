from rest_framework import serializers
from .models import ForecastRun, HourlyForecast


class ForecastRunCreateSerializer(serializers.Serializer):
    """Параметры запуска ML-пайплайна."""
    venue = serializers.IntegerField()
    process_data = serializers.BooleanField(default=True)
    train_model = serializers.BooleanField(default=True)
    make_forecast = serializers.BooleanField(default=True)
    evaluate = serializers.BooleanField(default=True)
    forecast_from = serializers.DateField(required=False, allow_null=True)
    forecast_to = serializers.DateField(required=False, allow_null=True)
    hours_ahead = serializers.IntegerField(default=720)  # 30 дней


class ForecastRunSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    triggered_by_name = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ForecastRun
        fields = [
            "id", "venue", "venue_name",
            "status", "status_display",
            "process_data", "train_model", "make_forecast", "evaluate",
            "forecast_from", "forecast_to", "hours_ahead",
            "accuracy_pct", "mae", "r2_score",
            "error_message",
            "triggered_by", "triggered_by_name",
            "started_at", "finished_at", "duration_seconds",
            "created_at",
        ]
        read_only_fields = fields

    def get_triggered_by_name(self, obj):
        if obj.triggered_by:
            return obj.triggered_by.get_full_name() or obj.triggered_by.username
        return None

    def get_duration_seconds(self, obj):
        if obj.started_at and obj.finished_at:
            return (obj.finished_at - obj.started_at).total_seconds()
        return None


class HourlyForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = HourlyForecast
        fields = [
            "forecast_datetime", "date", "hour",
            "day_of_week", "is_peak_hour", "is_weekend", "is_holiday",
            "orders_predicted", "orders_with_buffer",
            "guests_predicted", "guests_with_buffer",
        ]
        read_only_fields = fields


class DailyForecastSerializer(serializers.Serializer):
    """Агрегированный прогноз по дням (для менеджера)."""
    date = serializers.DateField()
    day_of_week = serializers.IntegerField()
    is_weekend = serializers.BooleanField()
    is_holiday = serializers.BooleanField()
    total_orders = serializers.FloatField()
    total_guests = serializers.FloatField()
    peak_hour_orders = serializers.FloatField()
    morning_orders = serializers.FloatField()   # 09-17
    evening_orders = serializers.FloatField()   # 17-01


class GenerateScheduleSerializer(serializers.Serializer):
    """Параметры генерации расписания."""
    venue = serializers.IntegerField()