from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from django.conf import settings
from django.db.models import Sum, Max, Min, Avg, Q, F
from django.db.models.functions import TruncDate
from pathlib import Path

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


class RunForecastView(APIView):
    """
    Р—Р°РїСѓСЃС‚РёС‚СЊ ML-РїР°Р№РїР»Р°Р№РЅ.

    ADMIN: РјРѕР¶РµС‚ РІСЃС‘ (process_data, train_model, make_forecast, evaluate).
    MANAGER: РјРѕР¶РµС‚ С‚РѕР»СЊРєРѕ make_forecast (РёСЃРїРѕР»СЊР·СѓРµС‚ СЃСѓС‰РµСЃС‚РІСѓСЋС‰СѓСЋ РјРѕРґРµР»СЊ).
    """
    permission_classes = [IsAuthenticated, IsManager]

    @extend_schema(
        request=ForecastRunCreateSerializer,
        responses={201: ForecastRunSerializer},
        summary="Р—Р°РїСѓСЃС‚РёС‚СЊ ML-РїР°Р№РїР»Р°Р№РЅ",
        tags=["forecast"],
    )
    def post(self, request):
        serializer = ForecastRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user

        # Manager может использовать только существующую модель/данные.
        if user.role == "manager":
            if data.get("process_data", False):
                return Response(
                    {"detail": "РћР±СЂР°Р±РѕС‚РєР° РґР°РЅРЅС‹С… РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if data.get("train_model", False):
                return Response(
                    {"detail": "РћР±СѓС‡РµРЅРёРµ РјРѕРґРµР»Рё РґРѕСЃС‚СѓРїРЅРѕ С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if data.get("evaluate", False):
                return Response(
                    {"detail": "РћС†РµРЅРєР° РјРѕРґРµР»Рё РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Если прогноз без обучения — файл модели должен уже существовать.
        if data.get("make_forecast", True) and not data.get("train_model", False):
            model_file = settings.ML_MODELS_DIR / "model_orders.pkl"
            if (not model_file.exists()) or model_file.stat().st_size == 0:
                return Response(
                    {
                        "detail": (
                            "РњРѕРґРµР»СЊ РЅРµ РЅР°Р№РґРµРЅР°. "
                            "РЎРЅР°С‡Р°Р»Р° Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ РґРѕР»Р¶РµРЅ РѕР±СѓС‡РёС‚СЊ РјРѕРґРµР»СЊ."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            venue = Venue.objects.get(id=data["venue"], is_active=True)
        except Venue.DoesNotExist:
            return Response({"detail": "РћР±СЉРµРєС‚ РЅРµ РЅР°Р№РґРµРЅ."}, status=404)

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
            Path(settings.ML_DATA_PREDICTED)
            / "runs"
            / f"venue_{venue.id}"
            / f"run_{run.id}"
        )

        try:
            runner = MLRunner(run)
            runner.execute(predicted_dir=run_outputs_dir, make_schedule=False)

            if run.make_forecast:
                try:
                    load_forecast_to_db(run, csv_path=run_outputs_dir / "forecast.csv")
                except ForecastLoadError as e:
                    run.error_message = f"РџР°Р№РїР»Р°Р№РЅ OK, РЅРѕ Р·Р°РіСЂСѓР·РєР° РїСЂРѕРіРЅРѕР·Р°: {e}"
                    run.save(update_fields=["error_message"])
        except Exception:
            pass

        run.refresh_from_db()

        response_serializer = ForecastRunSerializer(run)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class ForecastRunListView(ListAPIView):
    """РСЃС‚РѕСЂРёСЏ Р·Р°РїСѓСЃРєРѕРІ ML. РўРћР›Р¬РљРћ ADMIN."""
    serializer_class = ForecastRunSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = ForecastRun.objects.select_related("venue", "triggered_by")
        venue_id = self.request.query_params.get("venue")
        if venue_id:
            qs = qs.filter(venue_id=venue_id)
        return qs


class ForecastRunDetailView(APIView):
    """Р”РµС‚Р°Р»Рё РѕРґРЅРѕРіРѕ Р·Р°РїСѓСЃРєР° + РјРµС‚СЂРёРєРё."""
    permission_classes = [IsAuthenticated, IsAdmin] 

    def get(self, request, pk):
        try:
            run = ForecastRun.objects.select_related(
                "venue", "triggered_by"
            ).get(pk=pk)
        except ForecastRun.DoesNotExist:
            return Response({"detail": "РќРµ РЅР°Р№РґРµРЅРѕ."}, status=404)

        serializer = ForecastRunSerializer(run)
        return Response(serializer.data)


class HourlyForecastView(ListAPIView):
    """
    РџРѕС‡Р°СЃРѕРІРѕР№ РїСЂРѕРіРЅРѕР·.
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
            # РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ вЂ” РїРѕСЃР»РµРґРЅРёР№ СѓСЃРїРµС€РЅС‹Р№ run РґР»СЏ venue
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
    РђРіСЂРµРіРёСЂРѕРІР°РЅРЅС‹Р№ РїСЂРѕРіРЅРѕР· РїРѕ РґРЅСЏРј (СЃСѓРјРјР° Р·Р° РґРµРЅСЊ).
    РњРµРЅРµРґР¶РµСЂ РІРёРґРёС‚: РґР°С‚Р°, РІСЃРµРіРѕ Р·Р°РєР°Р·РѕРІ, СѓС‚СЂРѕРј, РІРµС‡РµСЂРѕРј.
    """
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        venue = request.query_params.get("venue")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if not venue:
            return Response(
                {"detail": "РЈРєР°Р¶РёС‚Рµ venue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # РќР°Р№С‚Рё РїРѕСЃР»РµРґРЅРёР№ СѓСЃРїРµС€РЅС‹Р№ run
        last_run = ForecastRun.objects.filter(
            venue_id=venue,
            status="completed",
        ).order_by("-created_at").first()

        if not last_run:
            return Response(
                {"detail": "РќРµС‚ Р·Р°РІРµСЂС€С‘РЅРЅС‹С… РїСЂРѕРіРЅРѕР·РѕРІ РґР»СЏ СЌС‚РѕРіРѕ РѕР±СЉРµРєС‚Р°."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = HourlyForecast.objects.filter(
            run=last_run, venue_id=venue
        )

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        # РђРіСЂРµРіР°С†РёСЏ РїРѕ РґРЅСЏРј
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
    """РњРµС‚СЂРёРєРё С‚РѕС‡РЅРѕСЃС‚Рё РїРѕСЃР»РµРґРЅРµР№ РѕР±СѓС‡РµРЅРЅРѕР№ РјРѕРґРµР»Рё."""
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
                {"detail": "РќРµС‚ РґР°РЅРЅС‹С… Рѕ С‚РѕС‡РЅРѕСЃС‚Рё РјРѕРґРµР»Рё."},
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
    DEPRECATED: РСЃРїРѕР»СЊР·СѓР№С‚Рµ POST /schedule/generate/ РІРјРµСЃС‚Рѕ СЌС‚РѕРіРѕ.
    РћСЃС‚Р°РІР»РµРЅРѕ РґР»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё. РўРћР›Р¬РљРћ ADMIN.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=GenerateScheduleSerializer,
        summary="РЎРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ СЂР°СЃРїРёСЃР°РЅРёРµ РёР· РїСЂРѕРіРЅРѕР·Р°",
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
                {"detail": "РћР±СЉРµРєС‚ РЅРµ РЅР°Р№РґРµРЅ."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # РџСЂРѕРІРµСЂРёС‚СЊ С‡С‚Рѕ РµСЃС‚СЊ РїСЂРѕРіРЅРѕР·
        has_forecast = ForecastRun.objects.filter(
            venue=venue,
            status="completed",
            make_forecast=True,
        ).exists()

        if not has_forecast:
            return Response(
                {"detail": "РЎРЅР°С‡Р°Р»Р° Р·Р°РїСѓСЃС‚РёС‚Рµ РїСЂРѕРіРЅРѕР· РґР»СЏ СЌС‚РѕРіРѕ РѕР±СЉРµРєС‚Р°."},
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
            "detail": "Р Р°СЃРїРёСЃР°РЅРёРµ СЃРѕР·РґР°РЅРѕ (С‡РµСЂРЅРѕРІРёРє).",
            **result,
        }, status=status.HTTP_201_CREATED)


class UploadRawDataView(APIView):
    """Р—Р°РіСЂСѓР·РёС‚СЊ СЃС‹СЂС‹Рµ РґР°РЅРЅС‹Рµ (Excel РёР»Рё CSV) РґР»СЏ РѕР±СѓС‡РµРЅРёСЏ РјРѕРґРµР»Рё."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "Р¤Р°Р№Р» РЅРµ РїРµСЂРµРґР°РЅ. РСЃРїРѕР»СЊР·СѓР№С‚Рµ РїРѕР»Рµ 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = uploaded_file.name.lower()

        # РћРїСЂРµРґРµР»РёС‚СЊ РєСѓРґР° СЃРѕС…СЂР°РЅСЏС‚СЊ
        if name.endswith(".csv"):
            dest_name = "real_orders.csv"
        elif name.endswith((".xlsx", ".xls")):
            dest_name = "real_orders.xlsx"
        else:
            return Response(
                {"detail": "Р”РѕРїСѓСЃС‚РёРјС‹Рµ С„РѕСЂРјР°С‚С‹: .csv, .xlsx, .xls"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import os
        dest_path = settings.ML_DATA_RAW / dest_name
        os.makedirs(settings.ML_DATA_RAW, exist_ok=True)

        with open(dest_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        return Response({
            "detail": "Р¤Р°Р№Р» Р·Р°РіСЂСѓР¶РµРЅ.",
            "path": str(dest_path),
            "filename": dest_name,
            "size_mb": round(uploaded_file.size / 1024 / 1024, 2),
        }, status=status.HTTP_201_CREATED)

