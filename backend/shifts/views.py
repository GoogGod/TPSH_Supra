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
from datetime import date
import calendar

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

        # Для employee: если список пуст, вернуть подсказку
        if request.user.is_employee and not response.data.get("results", response.data):
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
    3. Запускает scheduler (OR-Tools) → waiter_schedule.csv
    4. Парсит CSV → MonthlySchedule (draft)
    5. Возвращает созданное расписание

    Менеджер НЕ тренирует модель. Он использует то, что подготовил admin.
    """
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request):
        venue_id = request.data.get("venue")
        year = request.data.get("year")
        month = request.data.get("month")

        # ── Валидация ──
        if not venue_id:
            if request.user.venue:
                venue_id = request.user.venue_id
            else:
                return Response(
                    {"detail": "Укажите venue."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            venue = Venue.objects.get(id=venue_id, is_active=True)
        except Venue.DoesNotExist:
            return Response({"detail": "Объект не найден."}, status=404)

        # Определить год/месяц
        if not year or not month:
            today = date.today()
            if today.month == 12:
                year, month = today.year + 1, 1
            else:
                year, month = today.year, today.month + 1
        else:
            year, month = int(year), int(month)

        # ── Проверить что расписание ещё не создано ──
        existing = MonthlySchedule.objects.filter(
            venue=venue, year=year, month=month
        ).first()

        if existing:
            if existing.status == "published":
                return Response(
                    {"detail": f"Расписание на {month:02d}/{year} уже опубликовано."},
                    status=status.HTTP_409_CONFLICT,
                )
            else:
                # Черновик — удалить и перегенерировать
                existing.delete()

        # ── Проверить что модель обучена ──
        from forecasting.models import ForecastRun
        has_model = ForecastRun.objects.filter(
            status="completed",
            train_model=True,
        ).exists()

        if not has_model:
            return Response(
                {"detail": "Модель не обучена. Обратитесь к администратору."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Шаг 1: Прогноз на нужный месяц ──
        from forecasting.services.ml_runner import MLRunner
        from forecasting.services.forecast_loader import load_forecast_to_db, ForecastLoadError

        # Определить даты прогноза
        _, last_day = calendar.monthrange(year, month)
        forecast_from = date(year, month, 1)
        forecast_to = date(year, month, last_day)

        forecast_run = ForecastRun.objects.create(
            venue=venue,
            triggered_by=request.user,
            process_data=False,   # Данные уже обработаны админом
            train_model=False,    # Модель уже обучена админом
            make_forecast=True,
            evaluate=False,
            forecast_from=forecast_from,
            forecast_to=forecast_to,
        )

        try:
            runner = MLRunner(forecast_run)
            runner.execute()
        except Exception as e:
            return Response(
                {"detail": f"Ошибка прогноза: {forecast_run.error_message}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Загрузить прогнозы в БД
        try:
            load_forecast_to_db(forecast_run)
        except ForecastLoadError as e:
            return Response(
                {"detail": f"Прогноз создан, но ошибка загрузки: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ── Шаг 2: Генерация расписания ──
        from forecasting.services.schedule_generator import (
            generate_schedule_full,
            ScheduleGenerationError,
        )

        try:
            result = generate_schedule_full(venue)
        except ScheduleGenerationError as e:
            return Response(
                {"detail": f"Ошибка генерации расписания: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ── Вернуть созданное расписание ──
        schedule = MonthlySchedule.objects.prefetch_related(
            "slots__entries",
            "slots__assigned_employee",
        ).get(id=result["schedule_id"])

        from .serializers import MonthlyScheduleDetailSerializer
        serializer = MonthlyScheduleDetailSerializer(schedule)

        return Response({
            "detail": "Расписание сгенерировано (черновик).",
            "forecast_run_id": forecast_run.id,
            "schedule": serializer.data,
        }, status=status.HTTP_201_CREATED)