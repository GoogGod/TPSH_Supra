from pathlib import Path

from django.conf import settings
from django.db.models import Sum, Max, Min, Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shifts.models import Venue
from users.permissions import IsManager, IsAdmin

from .models import ForecastRun, HourlyForecast
from .serializers import (
    ForecastRunCreateSerializer,
    ForecastRunSerializer,
    HourlyForecastSerializer,
    DailyForecastSerializer,
    GenerateScheduleSerializer,
)
from .services.forecast_loader import load_forecast_to_db, ForecastLoadError
from .services.ml_runner import MLRunner
from .services.schedule_generator import generate_schedule_full, ScheduleGenerationError


class RunForecastView(APIView):
    """
    Запустить ML-пайплайн.

    ADMIN: может всё (process_data, train_model, make_forecast, evaluate).
    MANAGER: может только make_forecast на уже обученной модели.
    """

    permission_classes = [IsAuthenticated, IsManager]

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
        user = request.user

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

        if data.get("make_forecast", True) and not data.get("train_model", False):
            model_file = settings.ML_MODELS_DIR / "model_orders.pkl"
            if (not model_file.exists()) or model_file.stat().st_size == 0:
                return Response(
                    {
                        "detail": (
                            "Модель не найдена. "
                            "Сначала администратор должен обучить модель."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            venue = Venue.objects.get(id=data["venue"], is_active=True)
        except Venue.DoesNotExist:
            return Response({"detail": "Объект не найден."}, status=404)

        run = ForecastRun.objects.create(
            venue=venue,
            triggered_by=request.user,
            process_data=data.get("process_data", False),
            train_model=data.get("train_model", False),
            make_forecast=data.get("make_forecast", True),
            evaluate=data.get("evaluate", False),
            forecast_from=data.get("forecast_from"),
            forecast_to=data.get("forecast_to"),
            hours_ahead=data.get("hours_ahead", 720),
        )

        run_outputs_dir = (
            Path(settings.ML_DATA_PREDICTED) / "runs" / f"venue_{venue.id}" / f"run_{run.id}"
        )

        try:
            runner = MLRunner(run)
            runner.execute(predicted_dir=run_outputs_dir, make_schedule=False)

            if run.make_forecast:
                try:
                    load_forecast_to_db(run, csv_path=run_outputs_dir / "forecast.csv")
                except ForecastLoadError as e:
                    run.error_message = f"Пайплайн завершён, но загрузка прогноза не удалась: {e}"
                    run.save(update_fields=["error_message"])
        except Exception:
            pass

        run.refresh_from_db()
        return Response(ForecastRunSerializer(run).data, status=status.HTTP_201_CREATED)


class ForecastRunListView(ListAPIView):
    """История запусков ML. Только ADMIN."""

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
            run = ForecastRun.objects.select_related("venue", "triggered_by").get(pk=pk)
        except ForecastRun.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=404)

        return Response(ForecastRunSerializer(run).data)


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
        elif venue:
            last_run = (
                ForecastRun.objects.filter(venue_id=venue, status="completed")
                .order_by("-created_at")
                .first()
            )
            if last_run:
                qs = qs.filter(run=last_run)

        return qs


class DailyForecastView(APIView):
    """
    Агрегированный прогноз по дням (сумма за день).
    """

    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        venue = request.query_params.get("venue")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if not venue:
            return Response({"detail": "Укажите venue."}, status=status.HTTP_400_BAD_REQUEST)

        last_run = (
            ForecastRun.objects.filter(venue_id=venue, status="completed")
            .order_by("-created_at")
            .first()
        )

        if not last_run:
            return Response(
                {"detail": "Нет завершённых прогнозов для этого объекта."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = HourlyForecast.objects.filter(run=last_run, venue_id=venue)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        daily = (
            qs.values("date")
            .annotate(
                day_of_week=Min("day_of_week"),
                is_weekend=Max("is_weekend"),
                is_holiday=Max("is_holiday"),
                total_orders=Sum("orders_predicted"),
                total_guests=Sum("guests_predicted"),
                peak_hour_orders=Sum("orders_predicted", filter=Q(is_peak_hour=True)),
                morning_orders=Sum("orders_predicted", filter=Q(hour__gte=9, hour__lt=17)),
                evening_orders=Sum("orders_predicted", filter=Q(hour__gte=17) | Q(hour__lt=2)),
            )
            .order_by("date")
        )

        return Response(DailyForecastSerializer(daily, many=True).data)


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

        return Response(
            {
                "run_id": last_run.id,
                "venue": last_run.venue_id,
                "venue_name": last_run.venue.name,
                "accuracy_pct": last_run.accuracy_pct,
                "mae": last_run.mae,
                "r2_score": last_run.r2_score,
                "trained_at": last_run.finished_at,
                "forecast_from": last_run.forecast_from,
                "forecast_to": last_run.forecast_to,
            }
        )


class GenerateScheduleView(APIView):
    """
    DEPRECATED: используйте POST /schedule/generate/.
    Оставлено для обратной совместимости. Только ADMIN.
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
            return Response({"detail": "Объект не найден."}, status=status.HTTP_404_NOT_FOUND)

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
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "detail": "Расписание создано (черновик).",
                **result,
            },
            status=status.HTTP_201_CREATED,
        )


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

        return Response(
            {
                "detail": "Файл загружен.",
                "path": str(dest_path),
                "filename": dest_name,
                "size_mb": round(uploaded_file.size / 1024 / 1024, 2),
            },
            status=status.HTTP_201_CREATED,
        )
