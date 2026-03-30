from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db.models import Count, Q
from django.utils import timezone

from .models import Venue, MonthlySchedule, WaiterSlot
from .serializers import (
    VenueSerializer,
    MonthlyScheduleListSerializer,
    MonthlyScheduleDetailSerializer,
    WaiterSlotDetailSerializer,
)
from .services.csv_parser import parse_schedule_csv, CSVParseError
from users.permissions import IsManager, IsEmployee

from user_notifications.services import (
    notify_schedule_published,
    notify_slot_claimed,
    notify_manual_assignment,
    notify_assignment_response,
)


# ═══════════ Venues (без изменений) ═══════════

class VenueListView(ListAPIView):
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated, IsManager]
    pagination_class = None

    def get_queryset(self):
        return Venue.objects.filter(is_active=True)


# ═══════════ Загрузка CSV ═══════════

class UploadScheduleView(APIView):
    """Загрузить CSV от OR-Tools, создать черновик расписания."""
    permission_classes = [IsAuthenticated, IsManager]

    @extend_schema(
        summary="Загрузить CSV расписание",
        tags=["schedule"],
        request={"multipart/form-data": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "format": "binary"},
                "venue": {"type": "integer"},
            },
            "required": ["file", "venue"],
        }},
        responses={201: MonthlyScheduleDetailSerializer},
    )
    def post(self, request):
        csv_file = request.FILES.get("file")
        venue_id = request.data.get("venue")

        if not csv_file:
            return Response(
                {"detail": "Файл не передан. Используйте поле 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not venue_id:
            return Response(
                {"detail": "Укажите venue (id объекта)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            venue = Venue.objects.get(id=venue_id, is_active=True)
        except Venue.DoesNotExist:
            return Response(
                {"detail": "Объект не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            schedule = parse_schedule_csv(csv_file, venue)
        except CSVParseError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = MonthlyScheduleDetailSerializer(schedule)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ═══════════ Список / Детали расписания ═══════════

class MonthlyScheduleListView(ListAPIView):
    """Список расписаний. Менеджер — своё venue. Сотрудник — только published."""
    serializer_class = MonthlyScheduleListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = MonthlySchedule.objects.select_related("venue")

        # Сотрудник видит только опубликованные своего venue
        if user.is_employee:
            qs = qs.filter(venue=user.venue, status="published")
        elif user.is_manager:
            qs = qs.filter(venue=user.venue)
        # admin видит всё

        # Аннотации для total_slots / filled_slots
        qs = qs.annotate(
            total_slots=Count("slots"),
            filled_slots=Count("slots", filter=Q(
                slots__assignment_status__in=["pending", "confirmed"]
            )),
        )

        # Фильтры из query params
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)

        return qs


class MonthlyScheduleDetailView(APIView):
    """Детали расписания: все слоты + все записи."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.prefetch_related(
                "slots__entries",
                "slots__assigned_employee",
            ).select_related("venue").get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        # Сотрудник видит только published
        user = request.user
        if user.is_employee and schedule.status != "published":
            return Response({"detail": "Не найдено."}, status=404)
        if user.is_employee and schedule.venue != user.venue:
            return Response({"detail": "Не найдено."}, status=404)

        serializer = MonthlyScheduleDetailSerializer(schedule)
        return Response(serializer.data)


# ═══════════ Публикация ═══════════

class PublishScheduleView(APIView):
    """Опубликовать черновик → уведомить всех сотрудников."""
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        if schedule.status == "published":
            return Response(
                {"detail": "Расписание уже опубликовано."},
                status=status.HTTP_409_CONFLICT,
            )

        schedule.status = "published"
        schedule.published_at = timezone.now()
        schedule.published_by = request.user
        schedule.save()

        # Уведомить всех сотрудников
        notify_schedule_published(schedule)

        return Response({"detail": "Расписание опубликовано."})


# ═══════════ Удалить черновик ═══════════

class DeleteScheduleView(APIView):
    """Удалить черновик (менеджер не принял расписание)."""
    permission_classes = [IsAuthenticated, IsManager]

    def delete(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        if schedule.status == "published":
            return Response(
                {"detail": "Нельзя удалить опубликованное расписание."},
                status=status.HTTP_409_CONFLICT,
            )

        schedule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════ Claim (сотрудник сам занимает) ═══════════

class ClaimSlotView(APIView):
    """Сотрудник занимает свободную позицию."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if not user.is_employee:
            return Response(
                {"detail": "Только сотрудники могут занимать позиции."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            slot = WaiterSlot.objects.select_related(
                "schedule__venue"
            ).get(pk=pk)
        except WaiterSlot.DoesNotExist:
            return Response({"detail": "Позиция не найдена."}, status=404)

        # Проверки
        schedule = slot.schedule
        if schedule.status != "published":
            return Response(
                {"detail": "Расписание ещё не опубликовано."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if schedule.venue != user.venue:
            return Response(
                {"detail": "Вы не привязаны к этому объекту."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if slot.assignment_status != "open":
            return Response(
                {"detail": "Эта позиция уже занята."},
                status=status.HTTP_409_CONFLICT,
            )

        # Проверить что сотрудник не занял другой слот в этом расписании
        already = WaiterSlot.objects.filter(
            schedule=schedule,
            assigned_employee=user,
            assignment_status__in=["pending", "confirmed"],
        ).exists()
        if already:
            return Response(
                {"detail": "Вы уже заняли позицию в этом расписании."},
                status=status.HTTP_409_CONFLICT,
            )

        # Занять
        slot.assigned_employee = user
        slot.assignment_status = "confirmed"  # самозаявка = сразу confirmed
        slot.assigned_at = timezone.now()
        slot.confirmed_at = timezone.now()
        slot.save()

        notify_slot_claimed(slot)

        serializer = WaiterSlotDetailSerializer(slot)
        return Response(serializer.data)


# ═══════════ Assign (менеджер назначает) ═══════════

class AssignSlotView(APIView):
    """Менеджер назначает сотрудника на позицию. Требует подтверждения."""
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        from users.models import User

        employee_id = request.data.get("employee_id")
        if not employee_id:
            return Response(
                {"detail": "Укажите employee_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slot = WaiterSlot.objects.select_related(
                "schedule__venue"
            ).get(pk=pk)
        except WaiterSlot.DoesNotExist:
            return Response({"detail": "Позиция не найдена."}, status=404)

        try:
            employee = User.objects.get(
                pk=employee_id,
                role__in=["employee_noob", "employee_pro"],
                is_active=True,
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Сотрудник не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if slot.assignment_status != "open":
            return Response(
                {"detail": "Позиция уже занята."},
                status=status.HTTP_409_CONFLICT,
            )

        if employee.venue != slot.schedule.venue:
            return Response(
                {"detail": "Сотрудник не привязан к этому объекту."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверить что сотрудник не занял другой слот
        already = WaiterSlot.objects.filter(
            schedule=slot.schedule,
            assigned_employee=employee,
            assignment_status__in=["pending", "confirmed"],
        ).exists()
        if already:
            return Response(
                {"detail": "Сотрудник уже назначен на другую позицию."},
                status=status.HTTP_409_CONFLICT,
            )

        # Назначить с ожиданием подтверждения
        slot.assigned_employee = employee
        slot.assignment_status = "pending"
        slot.assigned_at = timezone.now()
        slot.save()

        notify_manual_assignment(slot)

        serializer = WaiterSlotDetailSerializer(slot)
        return Response(serializer.data)


# ═══════════ Unassign (менеджер снимает) ═══════════

class UnassignSlotView(APIView):
    """Менеджер снимает сотрудника с позиции."""
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            slot = WaiterSlot.objects.get(pk=pk)
        except WaiterSlot.DoesNotExist:
            return Response({"detail": "Позиция не найдена."}, status=404)

        if slot.assignment_status == "open":
            return Response(
                {"detail": "Позиция и так свободна."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slot.assigned_employee = None
        slot.assignment_status = "open"
        slot.assigned_at = None
        slot.confirmed_at = None
        slot.save()

        return Response({"detail": "Сотрудник снят с позиции."})