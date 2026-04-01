from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from django.conf import settings
from django.db.models import Sum, Max, Min, Avg, Q, F
from django.db.models.functions import TruncDate

from .models import ForecastRun, HourlyForecast
from .serializers import (
    ForecastRunCreateSerializer,
    ForecastRunSerializer,
    HourlyForecastSerializer,
    DailyForecastSerializer,
    GenerateScheduleSerializer,
)
from .services.ml_runner import MLRunner
from .services.forecast_loader import load_forecast_to_db, ForecastLoadError
from .services.schedule_generator import (
    generate_schedule_full,
    ScheduleGenerationError,
)
from shifts.models import Venue
from shifts.serializers import MonthlyScheduleDetailSerializer
from users.permissions import IsManager, IsAdmin

import calendar
from datetime import date

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import Venue, MonthlySchedule, WaiterSlot
from .serializers import (
    VenueSerializer,
    MonthlyScheduleListSerializer,
    MonthlyScheduleDetailSerializer,
    WaiterSlotDetailSerializer,
)
from .services.csv_parser import parse_schedule_csv, CSVParseError
from users.permissions import IsManager, IsEmployee, IsOnlyEmployee

from user_notifications.services import (
    notify_schedule_published,
    notify_slot_claimed,
    notify_manual_assignment,
    notify_assignment_response,
)


class RunForecastView(APIView):
    """
    Запустить ML-пайплайн.

    ADMIN: может всё (process_data, train_model, make_forecast, evaluate).
    MANAGER: может только make_forecast (использует существующую модель).
    """
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request):
        serializer = ForecastRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user

        # ── Менеджер не может тренировать модель ──
        if user.role == "manager":
            if data.get("process_data", False):
                return Response(
                    {"detail": "Обработка данных доступна только администратору."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if data.get("train_model", False):
                return Response(
                    {"detail": "Обучение модели доступно только администратору."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if data.get("evaluate", False):
                return Response(
                    {"detail": "Оценка модели доступна только администратору."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Принудительно выключить
            data["process_data"] = False
            data["train_model"] = False
            data["evaluate"] = False

    @extend_schema(
        request=ForecastRunCreateSerializer,
        responses={201: ForecastRunSerializer},
        summary="Запустить ML-пайплайн",
        tags=["forecast"],
    )
    def post(self, request):
        serializer = ForecastRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            venue = Venue.objects.get(id=data["venue"], is_active=True)
        except Venue.DoesNotExist:
            return Response({"detail": "Объект не найден."}, status=404)

        run = ForecastRun.objects.create(
            venue=venue,
            triggered_by=user,
            process_data=data.get("process_data", False),
            train_model=data.get("train_model", False),
            make_forecast=data.get("make_forecast", True),
            evaluate=data.get("evaluate", False),
            forecast_from=data.get("forecast_from"),
            forecast_to=data.get("forecast_to"),
            hours_ahead=data.get("hours_ahead", 720),
        )

        try:
            runner = MLRunner(run)
            runner.execute()

            if run.make_forecast:
                try:
                    load_forecast_to_db(run)
                except ForecastLoadError as e:
                    run.error_message = f"Пайплайн OK, но загрузка прогноза: {e}"
                    run.save(update_fields=["error_message"])
        except Exception:
            pass

        response_serializer = ForecastRunSerializer(run)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class ForecastRunListView(ListAPIView):
    """История запусков ML. ТОЛЬКО ADMIN."""
    serializer_class = ForecastRunSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = ForecastRun.objects.select_related("venue", "triggered_by")
        venue_id = self.request.query_params.get("venue")
        if venue_id:
            qs = qs.filter(venue_id=venue_id)
        return qs


class ForecastRunDetailView(APIView):
    """Детали одного запуска + метрики."""
    permission_classes = [IsAuthenticated, IsAdmin] 

    def get(self, request, pk):
        try:
            run = ForecastRun.objects.select_related(
                "venue", "triggered_by"
            ).get(pk=pk)
        except ForecastRun.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        serializer = ForecastRunSerializer(run)
        return Response(serializer.data)


class HourlyForecastView(ListAPIView):
    """
    Почасовой прогноз.
    Query params: venue, date_from, date_to, run_id
    """
    serializer_class = HourlyForecastSerializer
    permission_classes = [IsAuthenticated, IsManager]
    pagination_class = None

    def get_queryset(self):
        qs = HourlyForecast.objects.all()

        venue = self.request.query_params.get("venue")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        run_id = self.request.query_params.get("run_id")

        if venue:
            qs = qs.filter(venue_id=venue)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if run_id:
            qs = qs.filter(run_id=run_id)
        else:
            # По умолчанию — последний успешный run для venue
            if venue:
                last_run = ForecastRun.objects.filter(
                    venue_id=venue,
                    status="completed",
                ).order_by("-created_at").first()
                if last_run:
                    qs = qs.filter(run=last_run)

        return qs


class DailyForecastView(APIView):
    """
    Агрегированный прогноз по дням (сумма за день).
    Менеджер видит: дата, всего заказов, утром, вечером.
    """
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        venue = request.query_params.get("venue")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if not venue:
            return Response(
                {"detail": "Укажите venue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Найти последний успешный run
        last_run = ForecastRun.objects.filter(
            venue_id=venue,
            status="completed",
        ).order_by("-created_at").first()

        if not last_run:
            return Response(
                {"detail": "Нет завершённых прогнозов для этого объекта."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = HourlyForecast.objects.filter(
            run=last_run, venue_id=venue
        )

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        # Агрегация по дням
        daily = qs.values("date").annotate(
            day_of_week=Min("day_of_week"),
            is_weekend=Max("is_weekend"),
            is_holiday=Max("is_holiday"),
            total_orders=Sum("orders_predicted"),
            total_guests=Sum("guests_predicted"),
            peak_hour_orders=Sum(
                "orders_predicted",
                filter=Q(is_peak_hour=True),
            ),
            morning_orders=Sum(
                "orders_predicted",
                filter=Q(hour__gte=9, hour__lt=17),
            ),
            evening_orders=Sum(
                "orders_predicted",
                filter=Q(hour__gte=17) | Q(hour__lt=2),
            ),
        ).order_by("date")

        serializer = DailyForecastSerializer(daily, many=True)
        return Response(serializer.data)


class ModelAccuracyView(APIView):
    """Метрики точности последней обученной модели."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        venue = request.query_params.get("venue")

        qs = ForecastRun.objects.filter(
            status="completed",
            train_model=True,
            accuracy_pct__isnull=False,
        )
        if venue:
            qs = qs.filter(venue_id=venue)

        last_run = qs.order_by("-created_at").first()

        if not last_run:
            return Response(
                {"detail": "Нет данных о точности модели."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "run_id": last_run.id,
            "venue": last_run.venue_id,
            "venue_name": last_run.venue.name,
            "accuracy_pct": last_run.accuracy_pct,
            "mae": last_run.mae,
            "r2_score": last_run.r2_score,
            "trained_at": last_run.finished_at,
            "forecast_from": last_run.forecast_from,
            "forecast_to": last_run.forecast_to,
        })


class GenerateScheduleView(APIView):
    """
    DEPRECATED: Используйте POST /schedule/generate/ вместо этого.
    Оставлено для обратной совместимости. ТОЛЬКО ADMIN.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=GenerateScheduleSerializer,
        summary="Сгенерировать расписание из прогноза",
        tags=["forecast"],
    )
    def post(self, request):
        serializer = GenerateScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        venue_id = serializer.validated_data["venue"]

        try:
            venue = Venue.objects.get(id=venue_id, is_active=True)
        except Venue.DoesNotExist:
            return Response(
                {"detail": "Объект не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Проверить что есть прогноз
        has_forecast = ForecastRun.objects.filter(
            venue=venue,
            status="completed",
            make_forecast=True,
        ).exists()

        if not has_forecast:
            return Response(
                {"detail": "Сначала запустите прогноз для этого объекта."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = generate_schedule_full(venue)
        except ScheduleGenerationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "detail": "Расписание создано (черновик).",
            **result,
        }, status=status.HTTP_201_CREATED)


class UploadRawDataView(APIView):
    """Загрузить сырые данные (Excel или CSV) для обучения модели."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "Файл не передан. Используйте поле 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = uploaded_file.name.lower()

        # Определить куда сохранять
        if name.endswith(".csv"):
            dest_name = "real_orders.csv"
        elif name.endswith((".xlsx", ".xls")):
            dest_name = "real_orders.xlsx"
        else:
            return Response(
                {"detail": "Допустимые форматы: .csv, .xlsx, .xls"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import os
        dest_path = settings.ML_DATA_RAW / dest_name
        os.makedirs(settings.ML_DATA_RAW, exist_ok=True)

        with open(dest_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        return Response({
            "detail": "Файл загружен.",
            "path": str(dest_path),
            "filename": dest_name,
            "size_mb": round(uploaded_file.size / 1024 / 1024, 2),
        }, status=status.HTTP_201_CREATED)