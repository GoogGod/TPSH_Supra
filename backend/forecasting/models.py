from django.conf import settings
from django.db import models
from common.mixins import TimestampMixin


class ForecastRun(TimestampMixin):
    """
    Запуск ML-пайплайна. Трекает каждый вызов: обработка данных,
    обучение, прогноз. Хранит параметры и результаты.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "В очереди"
        PROCESSING = "processing", "Обработка данных"
        TRAINING = "training", "Обучение модели"
        FORECASTING = "forecasting", "Генерация прогноза"
        COMPLETED = "completed", "Завершён"
        FAILED = "failed", "Ошибка"

    venue = models.ForeignKey(
        "shifts.Venue",
        on_delete=models.CASCADE,
        related_name="forecast_runs",
        verbose_name="Объект",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Запустил",
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Статус",
        db_index=True,
    )

    # ── Параметры запуска ──
    process_data = models.BooleanField(default=True, verbose_name="Обработать данные")
    train_model = models.BooleanField(default=True, verbose_name="Обучить модель")
    make_forecast = models.BooleanField(default=True, verbose_name="Сделать прогноз")
    evaluate = models.BooleanField(default=True, verbose_name="Оценить точность")

    forecast_from = models.DateField(null=True, blank=True, verbose_name="Прогноз с")
    forecast_to = models.DateField(null=True, blank=True, verbose_name="Прогноз по")
    hours_ahead = models.PositiveIntegerField(default=720, verbose_name="Часов вперёд")

    # ── Результаты ──
    accuracy_pct = models.FloatField(null=True, blank=True, verbose_name="Точность %")
    mae = models.FloatField(null=True, blank=True, verbose_name="MAE")
    r2_score = models.FloatField(null=True, blank=True, verbose_name="R²")
    error_message = models.TextField(blank=True, default="", verbose_name="Ошибка")

    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Начало")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Конец")

    class Meta:
        db_table = "forecast_runs"
        verbose_name = "Запуск прогноза"
        verbose_name_plural = "Запуски прогнозов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Run #{self.pk} — {self.venue.name} [{self.get_status_display()}]"


class HourlyForecast(models.Model):
    """
    Одна строка почасового прогноза из forecast.csv.
    Загружается в БД после успешного запуска пайплайна
    для быстрого доступа через API.
    """
    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name="hourly_forecasts",
        verbose_name="Запуск",
    )
    venue = models.ForeignKey(
        "shifts.Venue",
        on_delete=models.CASCADE,
        related_name="hourly_forecasts",
        verbose_name="Объект",
    )

    forecast_datetime = models.DateTimeField(verbose_name="Дата и время")
    date = models.DateField(verbose_name="Дата", db_index=True)
    hour = models.PositiveSmallIntegerField(verbose_name="Час")
    day_of_week = models.PositiveSmallIntegerField(verbose_name="День недели")  # 0=пн

    is_peak_hour = models.BooleanField(default=False, verbose_name="Пиковый час")
    is_weekend = models.BooleanField(default=False, verbose_name="Выходной")
    is_holiday = models.BooleanField(default=False, verbose_name="Праздник")

    orders_predicted = models.FloatField(verbose_name="Заказы (прогноз)")
    orders_with_buffer = models.FloatField(verbose_name="Заказы (с буфером)")
    guests_predicted = models.FloatField(verbose_name="Гости (прогноз)")
    guests_with_buffer = models.FloatField(verbose_name="Гости (с буфером)")

    class Meta:
        db_table = "hourly_forecasts"
        verbose_name = "Почасовой прогноз"
        verbose_name_plural = "Почасовые прогнозы"
        ordering = ["forecast_datetime"]
        indexes = [
            models.Index(fields=["venue", "date"]),
        ]

    def __str__(self):
        return f"{self.forecast_datetime} — {self.orders_predicted} заказов"