from django.urls import path
from .views import (
    RunForecastView,
    ForecastRunListView,
    ForecastRunDetailView,
    HourlyForecastView,
    DailyForecastView,
    ModelAccuracyView,
    GenerateScheduleView,     # deprecated, оставлено для совместимости
    UploadRawDataView,
)

urlpatterns = [
    # ML — Admin only (кроме run/ с ограничениями)
    path("forecast/run/", RunForecastView.as_view(), name="forecast-run"),
    path("forecast/runs/", ForecastRunListView.as_view(), name="forecast-run-list"),
    path("forecast/runs/<int:pk>/", ForecastRunDetailView.as_view(), name="forecast-run-detail"),
    path("forecast/upload-data/", UploadRawDataView.as_view(), name="forecast-upload-data"),
    path("forecast/accuracy/", ModelAccuracyView.as_view(), name="forecast-accuracy"),

    # Прогнозы — Manager + Admin
    path("forecast/hourly/", HourlyForecastView.as_view(), name="forecast-hourly"),
    path("forecast/daily/", DailyForecastView.as_view(), name="forecast-daily"),

    # Deprecated
    path("forecast/generate-schedule/", GenerateScheduleView.as_view(), name="forecast-generate"),
]