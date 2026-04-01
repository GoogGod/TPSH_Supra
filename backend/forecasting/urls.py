from django.urls import path
from .views import (
    RunForecastView,
    ForecastRunListView,
    ForecastRunDetailView,
    HourlyForecastView,
    DailyForecastView,
    ModelAccuracyView,
    GenerateScheduleView,
    UploadRawDataView,
)

urlpatterns = [
    # Запуск и история
    path("forecast/run/", RunForecastView.as_view(), name="forecast-run"),
    path("forecast/runs/", ForecastRunListView.as_view(), name="forecast-run-list"),
    path("forecast/runs/<int:pk>/", ForecastRunDetailView.as_view(), name="forecast-run-detail"),

    # Результаты прогноза
    path("forecast/hourly/", HourlyForecastView.as_view(), name="forecast-hourly"),
    path("forecast/daily/", DailyForecastView.as_view(), name="forecast-daily"),

    # Метрики модели
    path("forecast/accuracy/", ModelAccuracyView.as_view(), name="forecast-accuracy"),

    # Генерация расписания
    path("forecast/generate-schedule/", GenerateScheduleView.as_view(), name="forecast-generate"),

    # Загрузка сырых данных
    path("forecast/upload-data/", UploadRawDataView.as_view(), name="forecast-upload-data"),
]