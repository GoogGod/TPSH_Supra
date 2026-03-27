import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from typing import Dict, Optional
import json
from pathlib import Path
from datetime import datetime
import joblib


def evaluate_model(
    model_path: str,
    data_path: str,
    feature_cols: list,
    target_column: str = 'orders_count',
    test_size: float = 0.2,
    verbose: bool = True
) -> Dict:
    if verbose:
        print("ОЦЕНКА МОДЕЛИ")
    
    # Загрузка модели
    model_data = joblib.load(model_path)
    model = model_data['model']
    saved_features = model_data.get('feature_cols', feature_cols)
    
    # Загрузка данных
    df = pd.read_csv(data_path, encoding='utf-8-sig')
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    
    if verbose:
        print(f"\nЗагружено {len(df)} записей")
        print(f"Диапазон: {df['datetime'].min()} — {df['datetime'].max()}")
    
    # Подготовка признаков
    df = _prepare_features(df)
    
    # Разделение на train/test
    split_idx = int(len(df) * (1 - test_size))
    df_train = df.iloc[:split_idx]
    df_test = df.iloc[split_idx:]
    
    X_test = df_test[saved_features]
    y_test = df_test[target_column]
    
    # Предсказание
    y_pred = model.predict(X_test)
    
    # Расчёт метрик
    metrics = _calculate_metrics(y_test, y_pred)
    
    
    if verbose:
        _print_report(metrics)
    
    return metrics


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    import holidays
    ru_holidays = holidays.Russia()
    
    df = df.copy()
    
    # Время
    df['hour'] = df['datetime'].dt.hour
    df['hour_encoded'] = np.sin(2 * np.pi * df['hour'] / 24)
    
    # Пиковые часы
    df['is_lunch_peak'] = ((df['hour'] >= 12) & (df['hour'] <= 14)).astype(int)
    df['is_dinner_peak'] = ((df['hour'] >= 18) & (df['hour'] <= 21)).astype(int)
    df['is_peak_hour'] = (df['is_lunch_peak'] | df['is_dinner_peak']).astype(int)
    
    # Календарь
    df['day_of_week'] = df['datetime'].dt.weekday
    df['month'] = df['datetime'].dt.month
    df['day_of_month'] = df['datetime'].dt.day
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['is_month_start'] = df['datetime'].dt.is_month_start.astype(int)
    df['is_month_end'] = df['datetime'].dt.is_month_end.astype(int)
    
    # Праздники
    df['is_holiday'] = df['datetime'].dt.date.apply(
        lambda x: 1 if x in ru_holidays else 0
    )
    
    # Взаимодействия
    df['hour_weekend'] = df['hour_encoded'] * df['is_weekend']
    df['hour_holiday'] = df['hour_encoded'] * df['is_holiday']
    df['peak_weekend'] = df['is_peak_hour'] * df['is_weekend']
    df['peak_holiday'] = df['is_peak_hour'] * df['is_holiday']
    
    # Дни
    df['friday_dinner'] = ((df['day_of_week'] == 4) & df['is_dinner_peak']).astype(int)
    df['saturday_dinner'] = ((df['day_of_week'] == 5) & df['is_dinner_peak']).astype(int)
    df['sunday_dinner'] = ((df['day_of_week'] == 6) & df['is_dinner_peak']).astype(int)
    
    # Лаги
    for lag in [1, 24, 168]:
        df[f'lag_orders_{lag}h'] = df['orders_count'].shift(lag)
    
    # Скользящие средние
    df['rolling_mean_3h'] = df['orders_count'].rolling(3, min_periods=1).mean()
    df['rolling_mean_24h'] = df['orders_count'].rolling(24, min_periods=1).mean()
    df['rolling_std_24h'] = df['orders_count'].rolling(24, min_periods=1).std()
    
    # Погода
    for col in ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']:
        if col not in df.columns:
            df[col] = 0
    
    df['rainy_peak'] = df['is_rainy'] * df['is_peak_hour']
    df['extreme_peak'] = df['is_extreme_weather'] * df['is_peak_hour']
    
    df = df.fillna(0)
    
    return df


def _calculate_metrics(y_true: pd.Series, y_pred: pd.Series) -> Dict:
    y_pred_rounded = np.maximum(0, np.round(y_pred)).astype(int)
    y_true_rounded = np.maximum(0, np.round(y_true)).astype(int)
    
    return {
        'test_mae': float(mean_absolute_error(y_true_rounded, y_pred_rounded)),
        'test_rmse': float(np.sqrt(mean_squared_error(y_true_rounded, y_pred_rounded))),
        'test_r2': float(r2_score(y_true_rounded, y_pred_rounded)),
        'mape': float(np.mean(np.abs((y_true_rounded - y_pred_rounded) / (y_true_rounded + 1))) * 100),
        'accuracy_within_1': float(np.mean(np.abs(y_true_rounded - y_pred_rounded) <= 1) * 100),
        'accuracy_within_2': float(np.mean(np.abs(y_true_rounded - y_pred_rounded) <= 2) * 100),
        'timestamp': datetime.now().isoformat()
    }

def _print_report(metrics: Dict):
    print(f"{'МЕТРИКИ МОДЕЛИ':^70}")
    print(f"{'Метрика':<35} {'Значение':>20}")
    print("-" * 70)
    print(f"{'MAE (средняя ошибка):':<35} {metrics.get('test_mae', 0):>20.2f}")
    print(f"{'RMSE (квадратичная ошибка):':<35} {metrics.get('test_rmse', 0):>20.2f}")
    print(f"{'R² (коэф. детерминации):':<35} {metrics.get('test_r2', 0):>20.3f}")
    print(f"{'MAPE (средняя % ошибка):':<35} {metrics.get('mape', 0):>20.1f}%")
    print(f"{'Точность (±1 заказ):':<35} {metrics.get('accuracy_within_1', 0):>20.1f}%")
    print(f"{'Точность (±2 заказа):':<35} {metrics.get('accuracy_within_2', 0):>20.1f}%")
