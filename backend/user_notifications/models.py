from django.conf import settings
from django.db import models
from common.mixins import TimestampMixin


class Notification(TimestampMixin):

    class Type(models.TextChoices):
        SCHEDULE_PUBLISHED = "schedule_published", "РќРѕРІРѕРµ СЂР°СЃРїРёСЃР°РЅРёРµ РѕРїСѓР±Р»РёРєРѕРІР°РЅРѕ"
        SLOT_CLAIMED = "slot_claimed", "РЎРѕС‚СЂСѓРґРЅРёРє Р·Р°РЅСЏР» РїРѕР·РёС†РёСЋ"
        MANUAL_ASSIGNMENT = "manual_assignment", "Ручное назначение"
        ASSIGNMENT_UNASSIGNED = "assignment_unassigned", "Назначение отменено"
        ASSIGNMENT_ACCEPTED = "assignment_accepted", "РќР°Р·РЅР°С‡РµРЅРёРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРѕ"
        ASSIGNMENT_REJECTED = "assignment_rejected", "РќР°Р·РЅР°С‡РµРЅРёРµ РѕС‚РєР»РѕРЅРµРЅРѕ"
        SCHEDULE_REMINDER = "schedule_reminder", "РќР°РїРѕРјРёРЅР°РЅРёРµ Рѕ СЂР°СЃРїРёСЃР°РЅРёРё"

    class ConfirmationStatus(models.TextChoices):
        NONE = "none", "РќРµ С‚СЂРµР±СѓРµС‚СЃСЏ"
        PENDING = "pending", "РћР¶РёРґР°РµС‚ РѕС‚РІРµС‚Р°"
        ACCEPTED = "accepted", "РџСЂРёРЅСЏС‚Рѕ"
        REJECTED = "rejected", "РћС‚РєР»РѕРЅРµРЅРѕ"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="РџРѕР»СѓС‡Р°С‚РµР»СЊ",
    )

    notification_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        verbose_name="РўРёРї",
        db_index=True,
    )

    title = models.CharField(max_length=255, verbose_name="Р—Р°РіРѕР»РѕРІРѕРє")
    message = models.TextField(verbose_name="РЎРѕРѕР±С‰РµРЅРёРµ")

    is_read = models.BooleanField(default=False, verbose_name="РџСЂРѕС‡РёС‚Р°РЅРѕ", db_index=True)

    # в”Ђв”Ђ РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ (РґР»СЏ manual_assignment) в”Ђв”Ђ
    requires_confirmation = models.BooleanField(default=False, verbose_name="РўСЂРµР±СѓРµС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ")
    confirmation_status = models.CharField(
        max_length=10,
        choices=ConfirmationStatus.choices,
        default=ConfirmationStatus.NONE,
        verbose_name="РЎС‚Р°С‚СѓСЃ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="РџРѕРґС‚РІРµСЂР¶РґРµРЅРѕ РІ")

    # в”Ђв”Ђ РЎРІСЏР·Рё СЃ СЂР°СЃРїРёСЃР°РЅРёРµРј (СЃС‚СЂРѕРєРѕРІС‹Рµ FK вЂ” Р±РµР· circular import) в”Ђв”Ђ
    related_schedule = models.ForeignKey(
        "shifts.MonthlySchedule",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="Р Р°СЃРїРёСЃР°РЅРёРµ",
    )
    related_slot = models.ForeignKey(
        "shifts.WaiterSlot",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="РџРѕР·РёС†РёСЏ",
    )

    class Meta:
        db_table = "notifications"
        verbose_name = "РЈРІРµРґРѕРјР»РµРЅРёРµ"
        verbose_name_plural = "РЈРІРµРґРѕРјР»РµРЅРёСЏ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_notification_type_display()}] в†’ {self.recipient}"
