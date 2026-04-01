import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from typing import Dict
import os
from src.config import RANDOM_STATE
from src.data.loader import load_raw_dataset
from src.data.preprocessor import prepare_features


def evaluate_model(
    model_path: str,
    data_path: str,
    feature_cols: list = None,
    target_column: str = 'orders_count',
    test_size: float = 0.2,
    verbose: bool = True
) -> Dict:
    if verbose:
        print("\nЗагружено {} записей".format(0))
    
    # Загружаем данные
    df = load_raw_dataset(data_path)
    
    if verbose:
        print(f"Загружено {len(df)} записей")
        print(f"Диапазон: {df['datetime'].min()} — {df['datetime'].max()}")
    
    # Генерируем признаки через prepare_features (как при обучении)
    df_agg, saved_features = prepare_features(df, verbose=False)
    
    # Загружаем модель
    model_data = joblib.load(model_path)
    model = model_data['model']
    
    # Используем признаки из модели (или переданные)
    if feature_cols is None:
        feature_cols = model_data.get('feature_cols', saved_features)
    
    # Проверяем наличие всех признаков
    missing_features = set(feature_cols) - set(df_agg.columns)
    if missing_features:
        if verbose:
            print(f"  Предупреждение: отсутствуют признаки: {missing_features}")
        # Добавляем отсутствующие признаки нулями
        for col in missing_features:
            df_agg[col] = 0
    
    # Доступные признаки
    available_features = [col for col in feature_cols if col in df_agg.columns]
    
    X = df_agg[available_features]
    y = df_agg[target_column]
    
    # Разделение на train/test (как при обучении)
    split_idx = int(len(df_agg) * (1 - test_size))
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    if verbose:
        print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Предсказания
    y_pred_test = model.predict(X_test)
    y_pred_test_rounded = np.maximum(0, np.round(y_pred_test)).astype(int)
    
    y_pred_train = model.predict(X_train)
    y_pred_train_rounded = np.maximum(0, np.round(y_pred_train)).astype(int)
    
    # Конверсия гостей
    avg_guests = model_data.get('avg_guests_per_order', 2.03)
    y_guests_pred = (y_pred_test_rounded * avg_guests).round().astype(int)
    y_guests_actual = (y_test * avg_guests).round().astype(int)
    
    # Метрики
    metrics = {
        'test_mae': float(mean_absolute_error(y_test, y_pred_test_rounded)),
        'test_rmse': float(np.sqrt(mean_squared_error(y_test, y_pred_test))),
        'test_r2': float(r2_score(y_test, y_pred_test)),
        'train_mae': float(mean_absolute_error(y_train, y_pred_train_rounded)),
        'train_rmse': float(np.sqrt(mean_squared_error(y_train, y_pred_train))),
        'train_r2': float(r2_score(y_train, y_pred_train)),
        'test_mape': float(np.mean(np.abs((y_test - y_pred_test_rounded) / np.maximum(y_test, 1))) * 100),
        'guests_mae': float(mean_absolute_error(y_guests_actual, y_guests_pred)),
        'guests_rmse': float(np.sqrt(mean_squared_error(y_guests_actual, y_guests_pred))),
        'guests_r2': float(r2_score(y_guests_actual, y_guests_pred)),
        'guests_mape': float(np.mean(np.abs((y_guests_actual - y_guests_pred) / np.maximum(y_guests_actual, 1))) * 100),
    }
    
    # Точность в процентах
    metrics['accuracy'] = 100 - metrics['test_mape']
    metrics['accuracy_within_10'] = float((np.abs(y_test - y_pred_test_rounded) <= y_test * 0.10).mean() * 100)
    metrics['accuracy_within_20'] = float((np.abs(y_test - y_pred_test_rounded) <= y_test * 0.20).mean() * 100)
    metrics['accuracy_within_30'] = float((np.abs(y_test - y_pred_test_rounded) <= y_test * 0.30).mean() * 100)
    metrics['accuracy_within_1_order'] = float((np.abs(y_test - y_pred_test_rounded) <= 1).mean() * 100)
    metrics['accuracy_within_2_orders'] = float((np.abs(y_test - y_pred_test_rounded) <= 2).mean() * 100)
    
    metrics['guests_accuracy'] = 100 - metrics['guests_mape']
    metrics['guests_accuracy_within_1'] = float((np.abs(y_guests_actual - y_guests_pred) <= 1).mean() * 100)
    metrics['guests_accuracy_within_2'] = float((np.abs(y_guests_actual - y_guests_pred) <= 2).mean() * 100)
    
    if verbose:
        print("\n" + " " * 28 + "МЕТРИКИ МОДЕЛИ")
        print("\n" + " " * 32 + "ЗАКАЗЫ")
        print("-" * 70)
        print(f"{'Метрика':<50} {'Значение':>15}")
        print("-" * 70)
        print(f"{'MAE (средняя ошибка)':<50} {metrics['test_mae']:>15.2f}")
        print(f"{'RMSE (квадратичная ошибка)':<50} {metrics['test_rmse']:>15.2f}")
        print(f"{'R² (коэф. детерминации)':<50} {metrics['test_r2']:>15.3f}")
        print(f"{'MAPE (средняя % ошибка)':<50} {metrics['test_mape']:>14.1f}%")
        print("\nТОЧНОСТЬ В ПРОЦЕНТАХ:")
        print(f"{'Общая точность (100% - MAPE)':<50} {metrics['accuracy']:>14.1f}%")
        print(f"{'Точность в пределах ±10%':<50} {metrics['accuracy_within_10']:>14.1f}%")
        print(f"{'Точность в пределах ±20%':<50} {metrics['accuracy_within_20']:>14.1f}%")
        print(f"{'Точность в пределах ±30%':<50} {metrics['accuracy_within_30']:>14.1f}%")
        print(f"\n{'Точность (±1 заказ)':<50} {metrics['accuracy_within_1_order']:>14.1f}%")
        print(f"{'Точность (±2 заказа)':<50} {metrics['accuracy_within_2_orders']:>14.1f}%")
        
        print("\n" + " " * 23 + "ГОСТИ (через конверсию)")
        print("-" * 70)
        print(f"{'Метрика':<50} {'Значение':>15}")
        print("-" * 70)
        print(f"{'MAE (средняя ошибка)':<50} {metrics['guests_mae']:>15.2f}")
        print(f"{'RMSE (квадратичная ошибка)':<50} {metrics['guests_rmse']:>15.2f}")
        print(f"{'R² (коэф. детерминации)':<50} {metrics['guests_r2']:>15.3f}")
        print(f"{'MAPE (средняя % ошибка)':<50} {metrics['guests_mape']:>14.1f}%")
        print("\nТОЧНОСТЬ В ПРОЦЕНТАХ:")
        print(f"{'Общая точность (100% - MAPE)':<50} {metrics['guests_accuracy']:>14.1f}%")
        print(f"{'Точность (±1 гость)':<50} {metrics['guests_accuracy_within_1']:>14.1f}%")
        print(f"{'Точность (±2 гостя)':<50} {metrics['guests_accuracy_within_2']:>14.1f}%")
        
        print("\n" + " " * 30 + "КОНВЕРСИЯ")
        print(f"{'Среднее гостей на заказ:':<50} {avg_guests:>15.2f}")
        
        # Оценка качества
        if metrics['test_r2'] >= 0.85:
            orders_rating = "ОТЛИЧНО"
        elif metrics['test_r2'] >= 0.70:
            orders_rating = "ХОРОШО"
        elif metrics['test_r2'] >= 0.50:
            orders_rating = "УДОВЛЕТВОРИТЕЛЬНО"
        else:
            orders_rating = "ТРЕБУЕТ УЛУЧШЕНИЯ"
        
        if metrics['guests_r2'] >= 0.80:
            guests_rating = "ОТЛИЧНО"
        elif metrics['guests_r2'] >= 0.65:
            guests_rating = "ХОРОШО"
        elif metrics['guests_r2'] >= 0.45:
            guests_rating = "УДОВЛЕТВОРИТЕЛЬНО"
        else:
            guests_rating = "ТРЕБУЕТ УЛУЧШЕНИЯ"
        
        print(f"\n{'Заказы:':<30} {orders_rating}")
        print(f"{'Гости:':<30} {guests_rating}")
    
    return metrics