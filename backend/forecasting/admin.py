from django.contrib import admin
from .models import ForecastRun, HourlyForecast


@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "venue", "status",
        "accuracy_pct", "mae", "r2_score",
        "forecast_from", "forecast_to",
        "triggered_by", "created_at",
    )
    list_filter = ("status", "venue")
    readonly_fields = (
        "started_at", "finished_at",
        "accuracy_pct", "mae", "r2_score",
        "error_message",
    )


@admin.register(HourlyForecast)
class HourlyForecastAdmin(admin.ModelAdmin):
    list_display = (
        "forecast_datetime", "venue",
        "orders_predicted", "guests_predicted",
        "is_peak_hour", "is_weekend", "is_holiday",
    )
    list_filter = ("venue", "is_peak_hour", "is_weekend", "is_holiday")
    date_hierarchy = "date"