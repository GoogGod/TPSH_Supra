from django.conf import settings
from django.db import models
from common.mixins import TimestampMixin


class Notification(TimestampMixin):

    class Type(models.TextChoices):
        SCHEDULE_PUBLISHED = "schedule_published", "Новое расписание опубликовано"
        SLOT_CLAIMED = "slot_claimed", "Сотрудник занял позицию"
        MANUAL_ASSIGNMENT = "manual_assignment", "Ручное назначение"
        ASSIGNMENT_ACCEPTED = "assignment_accepted", "Назначение подтверждено"
        ASSIGNMENT_REJECTED = "assignment_rejected", "Назначение отклонено"
        SCHEDULE_REMINDER = "schedule_reminder", "Напоминание о расписании"

    class ConfirmationStatus(models.TextChoices):
        NONE = "none", "Не требуется"
        PENDING = "pending", "Ожидает ответа"
        ACCEPTED = "accepted", "Принято"
        REJECTED = "rejected", "Отклонено"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Получатель",
    )

    notification_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        verbose_name="Тип",
        db_index=True,
    )

    title = models.CharField(max_length=255, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Сообщение")

    is_read = models.BooleanField(default=False, verbose_name="Прочитано", db_index=True)

    # ── Подтверждение (для manual_assignment) ──
    requires_confirmation = models.BooleanField(default=False, verbose_name="Требует подтверждения")
    confirmation_status = models.CharField(
        max_length=10,
        choices=ConfirmationStatus.choices,
        default=ConfirmationStatus.NONE,
        verbose_name="Статус подтверждения",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Подтверждено в")

    # ── Связи с расписанием (строковые FK — без circular import) ──
    related_schedule = models.ForeignKey(
        "shifts.MonthlySchedule",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="Расписание",
    )
    related_slot = models.ForeignKey(
        "shifts.WaiterSlot",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="Позиция",
    )

    class Meta:
        db_table = "notifications"
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_notification_type_display()}] → {self.recipient}"