from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Notification
from .serializers import NotificationSerializer
from .services import notify_assignment_response
from shifts.models import WaiterSlot


class NotificationListView(ListAPIView):
    """Мои уведомления (от новых к старым)."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class UnreadCountView(APIView):
    """Количество непрочитанных уведомлений."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
        return Response({"unread_count": count})


class MarkReadView(APIView):
    """Отметить уведомление как прочитанное."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(
                pk=pk, recipient=request.user
            )
        except Notification.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])
        return Response({"detail": "Прочитано."})


class MarkAllReadView(APIView):
    """Отметить все уведомления как прочитанные."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)
        return Response({"detail": f"Прочитано: {updated}"})


class ConfirmAssignmentView(APIView):
    """Сотрудник подтверждает ручное назначение."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.select_related(
                "related_slot"
            ).get(
                pk=pk,
                recipient=request.user,
                requires_confirmation=True,
                confirmation_status="pending",
            )
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Уведомление не найдено или уже обработано."},
                status=404,
            )

        now = timezone.now()

        # Обновить уведомление
        notification.confirmation_status = "accepted"
        notification.confirmed_at = now
        notification.is_read = True
        notification.save()

        # Обновить слот
        slot = notification.related_slot
        if slot:
            slot.assignment_status = "confirmed"
            slot.confirmed_at = now
            slot.save()
            notify_assignment_response(slot, accepted=True)

        return Response({"detail": "Назначение подтверждено."})


class RejectAssignmentView(APIView):
    """Сотрудник отклоняет ручное назначение."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.select_related(
                "related_slot"
            ).get(
                pk=pk,
                recipient=request.user,
                requires_confirmation=True,
                confirmation_status="pending",
            )
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Уведомление не найдено или уже обработано."},
                status=404,
            )

        # Обновить уведомление
        notification.confirmation_status = "rejected"
        notification.confirmed_at = timezone.now()
        notification.is_read = True
        notification.save()

        # Освободить слот
        slot = notification.related_slot
        if slot:
            employee_backup = slot.assigned_employee  # для уведомления
            notify_assignment_response(slot, accepted=False)
            slot.assigned_employee = None
            slot.assignment_status = "open"
            slot.assigned_at = None
            slot.confirmed_at = None
            slot.save()

        return Response({"detail": "Назначение отклонено."})