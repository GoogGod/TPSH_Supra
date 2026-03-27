from django.db import models
from common.mixins import TimestampMixin


class Venue(TimestampMixin):
    """
    Объект (ресторан/заведение).

    Прогнозная модель — одна на все заведения (обучается на общем датасете).
    Venue влияет только на оргструктуру: какие сотрудники привязаны,
    какие смены создаются.
    """
    name = models.CharField(
        max_length=255,
        verbose_name="Название",
    )
    address = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Адрес",
    )
    timezone = models.CharField(
        max_length=63,
        default="Europe/Moscow",
        verbose_name="Часовой пояс",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
    )

    class Meta:
        db_table = "venues"
        verbose_name = "Объект"
        verbose_name_plural = "Объекты"
        ordering = ["name"]

    def __str__(self):
        return self.name