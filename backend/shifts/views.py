from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Max
from django.utils import timezone

from .models import Venue, MonthlySchedule, WaiterSlot, ScheduleEntry
from .serializers import (
    VenueSerializer,
    VenueWriteSerializer,
    ScheduleEntryPatchSerializer,
    MonthlyScheduleListSerializer,
    MonthlyScheduleDetailSerializer,
    WaiterSlotDetailSerializer,
)
from .services.csv_parser import parse_schedule_csv, CSVParseError
from users.permissions import IsManager, IsAdmin
from datetime import date, time
import calendar
import csv
from pathlib import Path

from user_notifications.services import (
    notify_schedule_published,
    notify_slot_claimed,
    notify_manual_assignment,
    notify_assignment_unassigned,
    notify_assignment_response,
)


# ═══════════ Venues (без изменений) ═══════════

class VenueListView(ListAPIView):
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated, IsManager]
    pagination_class = None

    def get_queryset(self):
        return Venue.objects.filter(is_active=True)


class VenueCreateView(APIView):
    """Создать новый объект (ресторан)."""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Создать объект",
        tags=["schedule"],
        request=VenueWriteSerializer,
        responses={201: VenueSerializer},
    )
    def post(self, request):
        serializer = VenueWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        venue = serializer.save()
        return Response(VenueSerializer(venue).data, status=status.HTTP_201_CREATED)


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
    """
    Список расписаний.
    Employee: только published своего venue.
    Manager: всё своего venue.
    Admin: всё.
    """
    serializer_class = MonthlyScheduleListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = MonthlySchedule.objects.select_related("venue")

        if user.is_employee:
            if not user.venue:
                return MonthlySchedule.objects.none()
            qs = qs.filter(venue=user.venue, status="published")
        elif user.is_manager:
            qs = qs.filter(venue=user.venue)
        # admin видит всё

        venue_param = self.request.query_params.get("venue")
        if venue_param:
            try:
                venue_id = int(venue_param)
            except (TypeError, ValueError):
                return MonthlySchedule.objects.none()

            # Для manager/employee разрешаем только свой venue.
            if user.is_admin_role:
                qs = qs.filter(venue_id=venue_id)
            else:
                if not user.venue_id or user.venue_id != venue_id:
                    return MonthlySchedule.objects.none()
                qs = qs.filter(venue_id=venue_id)

        qs = qs.annotate(
            total_slots=Count("slots"),
            filled_slots=Count("slots", filter=Q(
                slots__assignment_status__in=["pending", "confirmed"]
            )),
        )

        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)

        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)

        payload = response.data
        items = payload.get("results", payload) if isinstance(payload, dict) else payload
        if request.user.is_employee and not items:
            return Response({
                "results": [],
                "message": "Опубликованных расписаний пока нет. Пожалуйста, подождите.",
            })

        return response


class MonthlyScheduleDetailView(APIView):
    """Детали расписания."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.prefetch_related(
                "slots__entries",
                "slots__assigned_employee",
            ).select_related("venue").get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        user = request.user

        # Employee видит только published своего venue
        if user.is_employee:
            if schedule.status != "published":
                return Response({
                    "detail": "Расписание ещё не опубликовано. Подождите.",
                    "exists": False,
                }, status=status.HTTP_404_NOT_FOUND)
            if schedule.venue != user.venue:
                return Response({"detail": "Не найдено."}, status=404)

        # Manager видит только своё venue
        if user.is_manager and not user.is_admin_role:
            if schedule.venue != user.venue:
                return Response({"detail": "Не найдено."}, status=404)

        serializer = MonthlyScheduleDetailSerializer(schedule)

        # Для employee: добавить инфо о его слоте
        data = serializer.data
        if user.is_employee:
            my_slot = schedule.slots.filter(
                assigned_employee=user,
                assignment_status__in=["pending", "confirmed"],
            ).first()
            data["my_slot"] = {
                "slot_id": my_slot.id,
                "waiter_num": my_slot.waiter_num,
                "status": my_slot.assignment_status,
            } if my_slot else None

        return Response(data)

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


class UnpublishScheduleView(APIView):
    """Вернуть опубликованное расписание в черновик."""
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.select_related("venue").get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        if request.user.is_manager and not request.user.is_admin_role:
            if not request.user.venue_id or request.user.venue_id != schedule.venue_id:
                return Response(
                    {"detail": "Доступ к этому расписанию запрещен."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if schedule.status == MonthlySchedule.Status.DRAFT:
            return Response(
                {"detail": "Расписание уже в черновике."},
                status=status.HTTP_409_CONFLICT,
            )

        schedule.status = MonthlySchedule.Status.DRAFT
        schedule.published_at = None
        schedule.published_by = None
        schedule.save(update_fields=["status", "published_at", "published_by", "updated_at"])

        return Response({"detail": "Расписание переведено в черновик."})


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


class UpdateDraftScheduleEntriesView(APIView):
    """
    Массово обновить записи расписания в ЧЕРНОВИКЕ.
    Полезно для ручной корректировки после генерации.
    """
    permission_classes = [IsAuthenticated, IsManager]

    @extend_schema(
        summary="Обновить записи черновика расписания",
        tags=["schedule"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "is_working": {"type": "boolean"},
                                "shift_type": {
                                    "type": "string",
                                    "enum": ["off", "full", "morning", "evening"],
                                },
                                "waiters_needed": {"type": "integer"},
                                "work_start": {"type": "string", "format": "time"},
                                "work_end": {"type": "string", "format": "time"},
                                "work_hours": {"type": "number"},
                            },
                            "required": ["id"],
                        },
                    }
                },
                "required": ["updates"],
            }
        },
    )
    def patch(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.select_related("venue").get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        user = request.user
        if user.is_manager and not user.is_admin_role:
            if not user.venue_id or user.venue_id != schedule.venue_id:
                return Response(
                    {"detail": "Доступ к этому расписанию запрещен."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if schedule.status != MonthlySchedule.Status.DRAFT:
            return Response(
                {"detail": "Редактировать можно только черновик."},
                status=status.HTTP_409_CONFLICT,
            )

        updates = request.data.get("updates")
        if not isinstance(updates, list) or not updates:
            return Response(
                {"detail": "Передайте непустой массив updates."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry_ids = []
        for item in updates:
            if not isinstance(item, dict):
                return Response(
                    {"detail": "Каждый элемент updates должен быть объектом."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "id" not in item:
                return Response(
                    {"detail": "У каждой записи updates должен быть id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                entry_ids.append(int(item["id"]))
            except (TypeError, ValueError):
                return Response(
                    {"detail": "id в updates должен быть числом."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        entries = {
            entry.id: entry
            for entry in ScheduleEntry.objects.filter(
                slot__schedule=schedule,
                id__in=set(entry_ids),
            )
        }
        missing = sorted(set(entry_ids) - set(entries.keys()))
        if missing:
            return Response(
                {
                    "detail": "Часть записей не найдена в этом расписании.",
                    "missing_entry_ids": missing,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        editable_fields = {
            "is_working",
            "shift_type",
            "waiters_needed",
            "work_start",
            "work_end",
            "work_hours",
        }
        prepared = []
        errors = {}

        for idx, item in enumerate(updates):
            if not any(field in item for field in editable_fields):
                errors[str(idx)] = {"detail": "Нет полей для изменения."}
                continue

            entry = entries[int(item["id"])]
            serializer = ScheduleEntryPatchSerializer(entry, data=item, partial=True)
            if serializer.is_valid():
                prepared.append(serializer)
            else:
                errors[str(idx)] = serializer.errors

        if errors:
            return Response(
                {
                    "detail": "Есть ошибки в updates.",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for serializer in prepared:
                serializer.save()
            MonthlySchedule.objects.filter(pk=schedule.pk).update(updated_at=timezone.now())

        schedule.refresh_from_db(fields=["updated_at"])
        return Response(
            {
                "detail": "Черновик расписания обновлен.",
                "schedule_id": schedule.id,
                "updated_entries_count": len(prepared),
                "updated_at": schedule.updated_at,
            },
            status=status.HTTP_200_OK,
        )


class AddDraftSlotView(APIView):
    """Добавить новую позицию официанта в черновик расписания."""
    permission_classes = [IsAuthenticated, IsManager]

    @extend_schema(
        summary="Добавить позицию в черновик расписания",
        tags=["schedule"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "employee_level": {
                        "type": "string",
                        "enum": ["employee_pro", "employee_noob"],
                        "nullable": True,
                    },
                    "waiters_needed": {
                        "type": "integer",
                        "minimum": 0,
                    },
                },
            }
        },
    )
    def post(self, request, pk):
        try:
            schedule = MonthlySchedule.objects.select_related("venue").get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        user = request.user
        if user.is_manager and not user.is_admin_role:
            if not user.venue_id or user.venue_id != schedule.venue_id:
                return Response(
                    {"detail": "Доступ к этому расписанию запрещен."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if schedule.status != MonthlySchedule.Status.DRAFT:
            return Response(
                {"detail": "Добавлять позиции можно только в черновик."},
                status=status.HTTP_409_CONFLICT,
            )

        employee_level = request.data.get("employee_level")
        if employee_level in ("", None):
            employee_level = None
        elif employee_level not in dict(WaiterSlot.EmployeeLevel.choices):
            return Response(
                {
                    "detail": "Некорректный employee_level.",
                    "allowed": list(dict(WaiterSlot.EmployeeLevel.choices).keys()),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        waiters_needed = request.data.get("waiters_needed")
        if waiters_needed in ("", None):
            waiters_needed = None
        else:
            try:
                waiters_needed = int(waiters_needed)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "waiters_needed должен быть целым числом >= 0."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if waiters_needed < 0:
                return Response(
                    {"detail": "waiters_needed должен быть целым числом >= 0."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        existing_dates = list(
            ScheduleEntry.objects.filter(slot__schedule=schedule)
            .order_by("date")
            .values_list("date", flat=True)
            .distinct()
        )
        if not existing_dates:
            return Response(
                {"detail": "В расписании нет дат для создания слота."},
                status=status.HTTP_409_CONFLICT,
            )

        if waiters_needed is None:
            day_need_map = {
                item["date"]: item["max_need"] or 0
                for item in ScheduleEntry.objects.filter(
                    slot__schedule=schedule,
                    date__in=existing_dates,
                )
                .values("date")
                .annotate(max_need=Max("waiters_needed"))
            }
        else:
            day_need_map = {d: waiters_needed for d in existing_dates}

        max_num = (
            WaiterSlot.objects.filter(schedule=schedule).aggregate(max_num=Max("waiter_num"))["max_num"] or 0
        )

        with transaction.atomic():
            slot = WaiterSlot.objects.create(
                schedule=schedule,
                waiter_num=max_num + 1,
                employee_level=employee_level,
                assignment_status=WaiterSlot.AssignmentStatus.OPEN,
            )
            entries = []
            first_work_date = existing_dates[0]
            for entry_date in existing_dates:
                is_first_day = entry_date == first_work_date
                entries.append(
                    ScheduleEntry(
                        slot=slot,
                        date=entry_date,
                        is_working=is_first_day,
                        shift_type=ScheduleEntry.ShiftType.FULL if is_first_day else ScheduleEntry.ShiftType.OFF,
                        waiters_needed=day_need_map.get(entry_date, 0),
                        work_start=time(10, 0) if is_first_day else None,
                        work_end=time(22, 0) if is_first_day else None,
                        work_hours=12 if is_first_day else 0,
                    )
                )
            ScheduleEntry.objects.bulk_create(entries)
            MonthlySchedule.objects.filter(pk=schedule.pk).update(updated_at=timezone.now())

        schedule.refresh_from_db(fields=["updated_at"])
        return Response(
            {
                "detail": "Позиция добавлена в черновик.",
                "schedule_id": schedule.id,
                "slot_id": slot.id,
                "waiter_num": slot.waiter_num,
                "employee_level": slot.employee_level,
                "entries_count": len(entries),
                "updated_at": schedule.updated_at,
            },
            status=status.HTTP_201_CREATED,
        )


class DeleteDraftSlotView(APIView):
    """Удалить позицию официанта из черновика расписания."""
    permission_classes = [IsAuthenticated, IsManager]

    def delete(self, request, pk, slot_id):
        try:
            schedule = MonthlySchedule.objects.select_related("venue").get(pk=pk)
        except MonthlySchedule.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        user = request.user
        if user.is_manager and not user.is_admin_role:
            if not user.venue_id or user.venue_id != schedule.venue_id:
                return Response(
                    {"detail": "Доступ к этому расписанию запрещен."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if schedule.status != MonthlySchedule.Status.DRAFT:
            return Response(
                {"detail": "Удалять позиции можно только в черновике."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            slot = WaiterSlot.objects.get(pk=slot_id, schedule=schedule)
        except WaiterSlot.DoesNotExist:
            return Response({"detail": "Позиция не найдена в этом расписании."}, status=404)

        deleted_slot_id = slot.id
        deleted_waiter_num = slot.waiter_num

        with transaction.atomic():
            slot.delete()
            MonthlySchedule.objects.filter(pk=schedule.pk).update(updated_at=timezone.now())

        schedule.refresh_from_db(fields=["updated_at"])
        remaining_slots = WaiterSlot.objects.filter(schedule=schedule).count()
        return Response(
            {
                "detail": "Позиция удалена из черновика.",
                "schedule_id": schedule.id,
                "slot_id": deleted_slot_id,
                "waiter_num": deleted_waiter_num,
                "remaining_slots": remaining_slots,
                "updated_at": schedule.updated_at,
            },
            status=status.HTTP_200_OK,
        )


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

        prev_employee = slot.assigned_employee
        slot.assigned_employee = None
        slot.assignment_status = "open"
        slot.assigned_at = None
        slot.confirmed_at = None
        slot.save()
        notify_assignment_unassigned(slot, prev_employee)

        return Response({"detail": "Сотрудник снят с позиции."})

class ScheduleStatusView(APIView):
    """
    Проверить статус расписания на месяц.

    Для каждой роли — свой ответ:
    - Manager: {exists, status, can_generate, schedule_id, slots_total, slots_filled}
    - Employee: {exists, published, schedule_id, message} или {exists: false, message: "Подождите"}
    - Admin: как Manager

    Query params: ?venue=1&year=2026&month=4
    Если year/month не указаны — берётся следующий месяц.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        venue_id = request.query_params.get("venue")
        year = request.query_params.get("year")
        month = request.query_params.get("month")

        # Определить venue
        if venue_id:
            try:
                venue = Venue.objects.get(id=venue_id, is_active=True)
            except Venue.DoesNotExist:
                return Response({"detail": "Объект не найден."}, status=404)
        elif user.venue:
            venue = user.venue
        else:
            return Response(
                {"detail": "Укажите venue или привяжите пользователя к объекту."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Определить год/месяц (по умолчанию — следующий месяц)
        if year and month:
            year = int(year)
            month = int(month)
        else:
            today = date.today()
            if today.month == 12:
                year, month = today.year + 1, 1
            else:
                year, month = today.year, today.month + 1

        # Найти расписание
        schedule = MonthlySchedule.objects.filter(
            venue=venue, year=year, month=month
        ).first()

        # ── Employee ──
        if user.is_employee:
            if schedule and schedule.status == "published":
                total = schedule.slots.count()
                filled = schedule.slots.exclude(assignment_status="open").count()
                open_slots = schedule.slots.filter(assignment_status="open").count()

                # Проверить занял ли сотрудник позицию
                my_slot = schedule.slots.filter(
                    assigned_employee=user,
                    assignment_status__in=["pending", "confirmed"],
                ).first()

                return Response({
                    "exists": True,
                    "published": True,
                    "schedule_id": schedule.id,
                    "year": year,
                    "month": month,
                    "venue_name": venue.name,
                    "slots_total": total,
                    "slots_filled": filled,
                    "slots_open": open_slots,
                    "my_slot": {
                        "slot_id": my_slot.id,
                        "waiter_num": my_slot.waiter_num,
                        "status": my_slot.assignment_status,
                    } if my_slot else None,
                })
            else:
                return Response({
                    "exists": False,
                    "published": False,
                    "year": year,
                    "month": month,
                    "venue_name": venue.name,
                    "message": f"Расписание на {month:02d}/{year} ещё не готово. Пожалуйста, подождите.",
                })

        # ── Manager / Admin ──
        if schedule:
            total = schedule.slots.count()
            filled = schedule.slots.exclude(assignment_status="open").count()

            return Response({
                "exists": True,
                "schedule_id": schedule.id,
                "status": schedule.status,
                "status_display": schedule.get_status_display(),
                "year": year,
                "month": month,
                "venue_name": venue.name,
                "slots_total": total,
                "slots_filled": filled,
                "slots_open": total - filled,
                "published_at": schedule.published_at,
                "can_generate": False,  # уже есть
            })
        else:
            # Проверить есть ли обученная модель
            from forecasting.models import ForecastRun
            has_model = ForecastRun.objects.filter(
                status="completed",
                train_model=True,
            ).exists()

            return Response({
                "exists": False,
                "year": year,
                "month": month,
                "venue_name": venue.name,
                "can_generate": has_model,
                "message": "Расписание не найдено."
                    if has_model
                    else "Расписание не найдено. Модель не обучена — обратитесь к администратору.",
            })
            
class GenerateMonthlyScheduleView(APIView):
    """
    Упрощённая генерация расписания для менеджера.

    Менеджер указывает venue + year + month.
    Бэкенд:
    1. Проверяет что модель обучена (admin уже сделал это)
    2. Запускает прогноз на нужный месяц (forecast)
    3. Запускает scheduler (OR-Tools) -> waiter_schedule.csv
    4. Парсит CSV -> MonthlySchedule (draft)
    5. Возвращает созданное расписание

    Менеджер НЕ тренирует модель. Он использует то, что подготовил admin.
    """
    permission_classes = [IsAuthenticated, IsManager]

    @staticmethod
    def _build_scheduler_profile(venue):
        """
        Подготовить профиль для scheduler из фактического состава venue.
        Новый scheduler использует долю noob, а не waiter_config по каждому номеру.
        """
        from users.models import User

        staff_qs = User.objects.filter(
            venue=venue,
            is_active=True,
            role__in=[User.Role.EMPLOYEE_PRO, User.Role.EMPLOYEE_NOOB],
        )

        total_staff = staff_qs.count()
        noob_count = staff_qs.filter(role=User.Role.EMPLOYEE_NOOB).count()
        noob_ratio = (noob_count / total_staff) if total_staff else 0.5
        noob_ratio = max(0.0, min(1.0, noob_ratio))

        return {
            "total_staff": total_staff,
            "noob_ratio": noob_ratio,
        }

    @staticmethod
    def _has_working_shifts(schedule_df) -> bool:
        if schedule_df is None or schedule_df.empty:
            return False

        if "shift_type_code" in schedule_df.columns:
            return bool((schedule_df["shift_type_code"] > 0).any())

        if "work_hours" in schedule_df.columns:
            try:
                return bool(schedule_df["work_hours"].fillna(0).astype(float).gt(0).any())
            except (TypeError, ValueError):
                return True

        return True

    @staticmethod
    def _csv_has_working_shifts(schedule_csv_path: Path) -> bool:
        if not schedule_csv_path.exists() or schedule_csv_path.stat().st_size == 0:
            return False

        try:
            with open(schedule_csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    shift_code_raw = str(row.get("shift_type_code", "")).strip()
                    if shift_code_raw:
                        try:
                            if int(float(shift_code_raw)) > 0:
                                return True
                        except ValueError:
                            pass

                    work_hours_raw = str(row.get("work_hours", "")).strip()
                    if work_hours_raw:
                        try:
                            if float(work_hours_raw) > 0:
                                return True
                        except ValueError:
                            pass
        except OSError:
            return False

        return False

    @staticmethod
    def _generate_schedule_fallback(
        *,
        forecast_csv_path: Path,
        schedule_csv_path: Path,
        noob_ratio: float,
    ):
        """
        Если main.py не создал waiter_schedule.csv, пробуем построить напрямую через scheduler.
        Новый scheduler не принимает waiter_config, поэтому повторяем генерацию
        с более мягкими параметрами min_hours_per_waiter.
        """
        if GenerateMonthlyScheduleView._csv_has_working_shifts(schedule_csv_path):
            return

        if not forecast_csv_path.exists() or forecast_csv_path.stat().st_size == 0:
            raise FileNotFoundError(f"Файл прогноза не найден: {forecast_csv_path}")

        import sys

        ml_data_path = str(settings.ML_DATA_DIR)
        if ml_data_path not in sys.path:
            sys.path.insert(0, ml_data_path)

        from ml_data.scheduler import create_waiter_schedule

        schedule_csv_path.parent.mkdir(parents=True, exist_ok=True)

        attempts = [
            (noob_ratio, 200),
            (noob_ratio, 160),
            (noob_ratio, 120),
            (0.5, 120),
            (0.5, 80),
            (0.5, 40),
            (0.5, 0),
        ]

        for ratio, min_hours in attempts:
            schedule_df, _ = create_waiter_schedule(
                forecast_path=str(forecast_csv_path),
                output_path=str(schedule_csv_path),
                min_hours_per_waiter=int(min_hours),
                best_effort=True,
                noob_ratio=float(ratio),
                verbose=False,
            )
            if GenerateMonthlyScheduleView._has_working_shifts(schedule_df):
                if not schedule_csv_path.exists() or schedule_csv_path.stat().st_size == 0:
                    raise FileNotFoundError(f"Файл расписания не создан: {schedule_csv_path}")
                return

        raise CSVParseError(
            "planner вернул пустое расписание (fallback исчерпан)"
        )

    @staticmethod
    def _calculate_staff_shortage(schedule: MonthlySchedule) -> dict:
        """
        Оценить нехватку сотрудников по сгенерированному расписанию.

        required_waiters_per_day: max(waiters_needed) за день.
        scheduled_slots_per_day: число рабочих слотов (is_working=True) за день.
        """
        from users.models import User

        available_staff = User.objects.filter(
            venue=schedule.venue,
            is_active=True,
            role__in=[User.Role.EMPLOYEE_PRO, User.Role.EMPLOYEE_NOOB],
        ).count()

        daily_rows = list(
            ScheduleEntry.objects.filter(slot__schedule=schedule)
            .values("date")
            .annotate(
                required_waiters=Max("waiters_needed"),
                scheduled_slots=Count("id", filter=Q(is_working=True)),
            )
            .order_by("date")
        )

        if not daily_rows:
            return {
                "available_staff": available_staff,
                "required_waiters_peak": 0,
                "lack_staff_peak": 0,
                "days_with_shortage": 0,
                "shortage_person_days": 0,
            }

        required_waiters_peak = 0
        days_with_shortage = 0
        shortage_person_days = 0

        for row in daily_rows:
            required = int(row.get("required_waiters") or 0)
            scheduled = int(row.get("scheduled_slots") or 0)
            shortage = max(0, required - scheduled)

            required_waiters_peak = max(required_waiters_peak, required)
            if shortage > 0:
                days_with_shortage += 1
                shortage_person_days += shortage

        lack_staff_peak = max(0, required_waiters_peak - available_staff)

        return {
            "available_staff": available_staff,
            "required_waiters_peak": required_waiters_peak,
            "lack_staff_peak": lack_staff_peak,
            "days_with_shortage": days_with_shortage,
            "shortage_person_days": shortage_person_days,
        }

    def post(self, request):
        venue_id = request.data.get("venue")
        year = request.data.get("year")
        month = request.data.get("month")

        if not venue_id:
            if request.user.venue:
                venue_id = request.user.venue_id
            else:
                return Response(
                    {"detail": "Укажите venue."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            venue_id = int(venue_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Некорректный venue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            venue = Venue.objects.get(id=venue_id, is_active=True)
        except Venue.DoesNotExist:
            return Response({"detail": "Объект не найден."}, status=404)

        # Manager работает только со своим venue.
        if request.user.is_manager and not request.user.is_admin_role:
            if not request.user.venue_id or venue_id != request.user.venue_id:
                return Response(
                    {"detail": "Доступ к этому объекту запрещен."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if not year or not month:
            today = date.today()
            if today.month == 12:
                year, month = today.year + 1, 1
            else:
                year, month = today.year, today.month + 1
        else:
            year, month = int(year), int(month)

        existing = MonthlySchedule.objects.filter(
            venue=venue, year=year, month=month
        ).first()

        if existing:
            if existing.status == "published":
                return Response(
                    {"detail": f"Расписание на {month:02d}/{year} уже опубликовано."},
                    status=status.HTTP_409_CONFLICT,
                )
            existing.delete()

        from forecasting.models import ForecastRun

        model_file = Path(settings.ML_MODELS_DIR) / "model_orders.pkl"
        has_model_run = ForecastRun.objects.filter(
            status="completed",
            train_model=True,
        ).exists()
        has_model_file = model_file.exists() and model_file.stat().st_size > 0
        has_model = has_model_run and has_model_file

        if not has_model:
            return Response(
                {
                    "detail": (
                        "Модель не обучена или файл модели отсутствует. "
                        "Обратитесь к администратору."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from forecasting.services.ml_runner import MLRunner
        from forecasting.services.forecast_loader import load_forecast_to_db, ForecastLoadError

        _, last_day = calendar.monthrange(year, month)
        forecast_from = date(year, month, 1)
        forecast_to = date(year, month, last_day)
        scheduler_profile = self._build_scheduler_profile(venue)
        noob_ratio = scheduler_profile["noob_ratio"]

        forecast_run = ForecastRun.objects.create(
            venue=venue,
            triggered_by=request.user,
            process_data=False,
            train_model=False,
            make_forecast=True,
            evaluate=False,
            forecast_from=forecast_from,
            forecast_to=forecast_to,
        )

        run_outputs_dir = (
            Path(settings.ML_DATA_PREDICTED)
            / "runs"
            / f"venue_{venue.id}"
            / f"run_{forecast_run.id}"
        )
        forecast_csv_path = run_outputs_dir / "forecast.csv"
        schedule_csv_path = run_outputs_dir / "waiter_schedule.csv"

        try:
            runner = MLRunner(forecast_run)
            runner.execute(
                predicted_dir=run_outputs_dir,
                make_schedule=True,
                pipeline_kwargs={
                    "noob_ratio": noob_ratio,
                },
            )
        except Exception:
            return Response(
                {"detail": f"Ошибка прогноза: {forecast_run.error_message}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            load_forecast_to_db(forecast_run, csv_path=forecast_csv_path)
        except ForecastLoadError as e:
            return Response(
                {"detail": f"Прогноз создан, но ошибка загрузки: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            self._generate_schedule_fallback(
                forecast_csv_path=forecast_csv_path,
                schedule_csv_path=schedule_csv_path,
                noob_ratio=noob_ratio,
            )
            with open(schedule_csv_path, "r", encoding="utf-8-sig") as f:
                csv_content = f.read()
            schedule = parse_schedule_csv(csv_content, venue)
        except (CSVParseError, FileNotFoundError) as e:
            return Response(
                {"detail": f"Ошибка генерации расписания: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if schedule.year != year or schedule.month != month:
            schedule.delete()
            return Response(
                {
                    "detail": (
                        f"Сгенерировано некорректное окно: {schedule.month:02d}/{schedule.year}, "
                        f"ожидалось {month:02d}/{year}."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        slots_count = schedule.slots.count()
        entries_count = schedule.slots.aggregate(total_entries=Count("entries"))["total_entries"] or 0
        shortage = self._calculate_staff_shortage(schedule)

        return Response(
            {
                "detail": "Расписание сгенерировано (черновик).",
                "schedule_id": schedule.id,
                "year": schedule.year,
                "month": schedule.month,
                "slots_count": slots_count,
                "entries_count": entries_count,
                "forecast_run_id": forecast_run.id,
                "artifacts_dir": str(run_outputs_dir),
                "available_staff": shortage["available_staff"],
                "required_waiters_peak": shortage["required_waiters_peak"],
                "lack_staff_peak": shortage["lack_staff_peak"],
                "days_with_shortage": shortage["days_with_shortage"],
                "shortage_person_days": shortage["shortage_person_days"],
            },
            status=status.HTTP_201_CREATED,
        )

