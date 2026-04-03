import os
import sys
import traceback
from pathlib import Path
from threading import Lock

from django.conf import settings
from django.utils import timezone

from forecasting.models import ForecastRun

_ML_PIPELINE_LOCK = Lock()


class MLRunner:

    def __init__(self, forecast_run: ForecastRun):
        self.run = forecast_run
        self.original_cwd = os.getcwd()
        self.original_path = sys.path.copy()

    def execute(
        self,
        *,
        predicted_dir: Path = None,
        make_schedule: bool = False,
        pipeline_kwargs: dict | None = None,
    ):
        try:
            self._update_status(ForecastRun.Status.PROCESSING)
            self.run.started_at = timezone.now()
            self.run.save(update_fields=["started_at", "status", "updated_at"])

            ml_data_path = str(settings.ML_DATA_DIR)
            if ml_data_path not in sys.path:
                sys.path.insert(0, ml_data_path)

            os.chdir(settings.ML_DATA_DIR)

            from ml_data import main as ml_main_module

            kwargs = {
                "process_data": self.run.process_data,
                "train_model": self.run.train_model,
                "make_forecast": self.run.make_forecast,
                "evaluate": self.run.evaluate,
                "make_schedule": make_schedule,
                "verbose": False,
            }
            if pipeline_kwargs:
                kwargs.update(pipeline_kwargs)

            if self.run.forecast_from:
                kwargs["from_date"] = self.run.forecast_from.strftime("%Y-%m-%d")
            if self.run.forecast_to:
                # DateField in ForecastRun is inclusive by calendar day.
                # Pass end-of-day timestamp so ML range includes the whole last day.
                kwargs["to_date"] = f"{self.run.forecast_to.strftime('%Y-%m-%d')} 23:59:59"
            if not self.run.forecast_from and not self.run.forecast_to:
                kwargs["hours_ahead"] = self.run.hours_ahead

            if self.run.train_model:
                self._update_status(ForecastRun.Status.TRAINING)
            if self.run.make_forecast:
                self._update_status(ForecastRun.Status.FORECASTING)

            with _ML_PIPELINE_LOCK:
                original_pred_dir = ml_main_module.DATA_PRED_DIR
                if predicted_dir is not None:
                    predicted_dir = Path(predicted_dir)
                    predicted_dir.mkdir(parents=True, exist_ok=True)
                    ml_main_module.DATA_PRED_DIR = str(predicted_dir)

                try:
                    result = ml_main_module.main(**kwargs)
                finally:
                    ml_main_module.DATA_PRED_DIR = original_pred_dir

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
            os.chdir(self.original_cwd)
            sys.path = self.original_path

    def _update_status(self, new_status):
        self.run.status = new_status
        self.run.save(update_fields=["status", "updated_at"])

    def _extract_metrics(self, result):
        updated = False
        if isinstance(result, dict):
            updated = self._apply_metrics(result)

        if not updated:
            try:
                self._load_metrics_from_model()
            except Exception:
                pass

    def _first_float(self, data: dict, keys: list[str]):
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if value != value:  # NaN
                continue
            return value
        return None

    def _apply_metrics(self, metrics: dict) -> bool:
        if not isinstance(metrics, dict):
            return False

        mae = self._first_float(metrics, ["mae", "test_mae", "val_mae"])
        r2 = self._first_float(metrics, ["r2_score", "r2", "test_r2"])
        accuracy = self._first_float(
            metrics,
            ["accuracy_pct", "accuracy", "acc", "test_accuracy"],
        )

        if accuracy is None:
            mape = self._first_float(metrics, ["mape", "test_mape"])
            if mape is not None:
                accuracy = max(0.0, 100.0 - mape)

        # Fallback: if only R2 is available, convert to percent-like value for API.
        if accuracy is None and r2 is not None:
            accuracy = max(0.0, min(100.0, r2 * 100.0))

        if accuracy is not None and 0.0 <= accuracy <= 1.0:
            accuracy *= 100.0

        changed_fields = []
        if accuracy is not None and self.run.accuracy_pct != accuracy:
            self.run.accuracy_pct = accuracy
            changed_fields.append("accuracy_pct")
        if mae is not None and self.run.mae != mae:
            self.run.mae = mae
            changed_fields.append("mae")
        if r2 is not None and self.run.r2_score != r2:
            self.run.r2_score = r2
            changed_fields.append("r2_score")

        if changed_fields:
            changed_fields.append("updated_at")
            self.run.save(update_fields=changed_fields)
            return True

        return False

    def _load_metrics_from_model(self):
        import joblib

        model_path = settings.ML_MODELS_DIR / "model_orders.pkl"
        if not model_path.exists():
            return

        model_data = joblib.load(model_path)
        if not isinstance(model_data, dict):
            return

        candidates = [
            model_data.get("metrics"),
            model_data.get("meta"),
            model_data,
        ]
        for candidate in candidates:
            if isinstance(candidate, dict) and self._apply_metrics(candidate):
                return
