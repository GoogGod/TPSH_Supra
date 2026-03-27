import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from typing import Dict, Optional


def evaluate_predictions(
    y_true: pd.Series,
    y_pred: pd.Series,
    df_details: Optional[pd.DataFrame] = None,
    verbose: bool = True
) -> Dict:
    """
    Оценивает качество предсказаний.
    
    Параметры:
        y_true: Фактические значения
        y_pred: Предсказанные значения
        df_details: DataFrame с деталями (дата, смена и т.д.)
        verbose: Выводить отчет
    
    Возвращает:
        metrics: Словарь с метриками
    """
    y_pred_rounded = np.maximum(1, np.round(y_pred)).astype(int)
    
    metrics = {
        'mae': mean_absolute_error(y_true, y_pred_rounded),
        'rmse': np.sqrt(mean_squared_error(y_true, y_pred_rounded)),
        'r2': r2_score(y_true, y_pred_rounded),
        'mape': np.mean(np.abs((y_true - y_pred_rounded) / y_true)) * 100,
        'accuracy_within_1': np.mean(np.abs(y_true - y_pred_rounded) <= 1) * 100,
        'accuracy_within_2': np.mean(np.abs(y_true - y_pred_rounded) <= 2) * 100,
    }
    
    if verbose:
        print("ОЦЕНКА КАЧЕСТВА ПРОГНОЗА")
        print(f"MAE: {metrics['mae']:.2f} официанта")
        print(f"RMSE: {metrics['rmse']:.2f}")
        print(f"R2: {metrics['r2']:.3f}")
        print(f"MAPE: {metrics['mape']:.1f}%")
        print(f"Точность (±1): {metrics['accuracy_within_1']:.1f}%")
        print(f"Точность (±2): {metrics['accuracy_within_2']:.1f}%")
    
    if df_details is not None:
        df_details = df_details.copy()
        df_details['y_true'] = y_true.values
        df_details['y_pred'] = y_pred_rounded
        df_details['error'] = df_details['y_true'] - df_details['y_pred']
        df_details['abs_error'] = np.abs(df_details['error'])
        
        if 'day_type' in df_details.columns:
            by_day_type = df_details.groupby('day_type').agg({
                'abs_error': ['mean', 'std', 'count']
            }).round(2)
            if verbose:
                print("Ошибка по типам дней:")
                print(by_day_type)
        
        if 'shift' in df_details.columns:
            by_shift = df_details.groupby('shift').agg({
                'abs_error': ['mean', 'count']
            }).round(2)
            if verbose:
                print("Ошибка по сменам:")
                print(by_shift)
    
    return metrics