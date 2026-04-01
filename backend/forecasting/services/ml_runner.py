import os
import sys
import traceback

from django.conf import settings
from django.utils import timezone

from forecasting.models import ForecastRun


class MLRunner:

    def __init__(self, forecast_run: ForecastRun):
        self.run = forecast_run
        self.original_cwd = os.getcwd()
        self.original_path = sys.path.copy()

    def execute(self):
        try:
            self._update_status(ForecastRun.Status.PROCESSING)
            self.run.started_at = timezone.now()
            self.run.save(update_fields=["started_at", "status", "updated_at"])

            # ═══ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ═══
            # ml_data/main.py использует `from src.xxx import ...`
            # Для этого ml_data/ должна быть в sys.path
            ml_data_path = str(settings.ML_DATA_DIR)
            if ml_data_path not in sys.path:
                sys.path.insert(0, ml_data_path)

            # Переключить рабочую директорию (для относительных путей в ML-коде)
            os.chdir(settings.ML_DATA_DIR)
            # ═════════════════════════════

            from ml_data.main import main as ml_main

            kwargs = {
                "process_data": self.run.process_data,
                "train_model": self.run.train_model,
                "make_forecast": self.run.make_forecast,
                "evaluate": self.run.evaluate,
                "verbose": False,
            }

            if self.run.forecast_from:
                kwargs["from_date"] = self.run.forecast_from.strftime("%Y-%m-%d")
            if self.run.forecast_to:
                kwargs["to_date"] = self.run.forecast_to.strftime("%Y-%m-%d")
            if not self.run.forecast_from and not self.run.forecast_to:
                kwargs["hours_ahead"] = self.run.hours_ahead

            if self.run.train_model:
                self._update_status(ForecastRun.Status.TRAINING)
            if self.run.make_forecast:
                self._update_status(ForecastRun.Status.FORECASTING)

            result = ml_main(**kwargs)

            self._extract_metrics(result)

            self._update_status(ForecastRun.Status.COMPLETED)
            self.run.finished_at = timezone.now()
            self.run.save()

        except Exception as e:
            self.run.status = ForecastRun.Status.FAILED
            self.run.error_message = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            self.run.finished_at = timezone.now()
            self.run.save()
            raise

        finally:
            # Восстановить рабочую директорию и sys.path
            os.chdir(self.original_cwd)
            sys.path = self.original_path

    def _update_status(self, new_status):
        self.run.status = new_status
        self.run.save(update_fields=["status", "updated_at"])

    def _extract_metrics(self, result):
        if isinstance(result, dict):
            self.run.accuracy_pct = result.get("accuracy_pct")
            self.run.mae = result.get("mae")
            self.run.r2_score = result.get("r2_score")
            self.run.save(update_fields=[
                "accuracy_pct", "mae", "r2_score", "updated_at"
            ])
            return

        try:
            self._load_metrics_from_model()
        except Exception:
            pass

    def _load_metrics_from_model(self):
        import joblib
        model_path = settings.ML_MODELS_DIR / "model_orders.pkl"
        if not model_path.exists():
            return

        model_data = joblib.load(model_path)
        if not isinstance(model_data, dict):
            return

        metrics = model_data.get("metrics")
        if not isinstance(metrics, dict):
            meta = model_data.get("meta")
            metrics = meta if isinstance(meta, dict) else {}

        # Поддержка разных названий метрик в новых моделях.
        self.run.accuracy_pct = (
            metrics.get("accuracy_pct")
            or metrics.get("accuracy")
            or metrics.get("acc")
        )
        self.run.mae = metrics.get("mae")
        self.run.r2_score = (
            metrics.get("r2_score")
            or metrics.get("r2")
            or metrics.get("test_r2")
        )
        self.run.save(update_fields=[
            "accuracy_pct", "mae", "r2_score", "updated_at"
        ])
