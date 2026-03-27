import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
from typing import Tuple
import warnings
import os
from src.config import MODEL_PARAMS, TEST_SIZE, RANDOM_STATE, TARGET_COLUMN

warnings.filterwarnings('ignore')


def train(
    df_agg: pd.DataFrame,
    feature_cols: list,
    model_type: str = 'gradient_boosting',
    test_size: float = None,
    random_state: int = None,
    model_path: str = None,
    verbose: bool = True
) -> Tuple[object, dict]:
    test_size = test_size or TEST_SIZE
    random_state = random_state or RANDOM_STATE
    
    if verbose:
        print("ОБУЧЕНИЕ МОДЕЛИ")
        print(f"Всего записей в df_agg: {len(df_agg)}")
        print(f"Колонки в df_agg: {list(df_agg.columns)}")
    
    # Проверка: достаточно ли данных
    if len(df_agg) < 100:
        raise ValueError(f"Слишком мало данных для обучения: {len(df_agg)} записей. Минимум 100.")
    
    # Проверка: есть ли целевая переменная
    if TARGET_COLUMN not in df_agg.columns:
        raise ValueError(f"Целевая переменная '{TARGET_COLUMN}' не найдена. Доступные: {list(df_agg.columns)}")
    
    # Проверка: есть ли признаки
    available_features = [col for col in feature_cols if col in df_agg.columns]
    if len(available_features) == 0:
        raise ValueError(f"Ни один признак не найден. Ожидалось: {feature_cols[:5]}...")
    
    if verbose:
        print(f"Используемые признаки: {len(available_features)}")
    
    X = df_agg[available_features]
    y = df_agg[TARGET_COLUMN]
    
    # Проверка на NaN/Inf
    if X.isnull().any().any():
        if verbose:
            print(f"Предупреждение: есть NaN в признаках. Заполняем нулями.")
        X = X.fillna(0)
    
    if y.isnull().any():
        if verbose:
            print(f"Предупреждение: есть NaN в целевой переменной. Заполняем медианой.")
        y = y.fillna(y.median())
    
    # Разделение с учётом временного ряда
    split_idx = int(len(df_agg) * (1 - test_size))
    
    if verbose:
        print(f"Разделение: всего={len(df_agg)}, train={split_idx}, test={len(df_agg) - split_idx}")
    
    if split_idx < 10:
        raise ValueError(f"Слишком мало данных для train: {split_idx}. Уменьшите test_size или добавьте данных.")
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    if verbose:
        print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    if len(X_train) == 0:
        raise ValueError("X_train пустой! Проверьте данные и параметры разделения.")
    
    if len(X_test) == 0:
        if verbose:
            print("Предупреждение: X_test пустой. Используем весь набор для обучения.")
        X_test = X_train
        y_test = y_train
    
    if verbose:
        print(f"Признаков: {len(available_features)}")
    
    if model_type == 'random_forest':
        params = MODEL_PARAMS['random_forest']
        model = RandomForestRegressor(**params)
    elif model_type == 'gradient_boosting':
        params = MODEL_PARAMS['gradient_boosting']
        model = GradientBoostingRegressor(**params)
    else:
        raise ValueError(f"Неизвестный тип модели: {model_type}")
    
    if verbose:
        print(f"Обучение {model_type}...")
    
    model.fit(X_train, y_train)
    
    y_pred_test = model.predict(X_test)
    y_pred_test_rounded = np.maximum(0, np.round(y_pred_test)).astype(int)
    
    y_pred_train = model.predict(X_train)
    y_pred_train_rounded = np.maximum(0, np.round(y_pred_train)).astype(int)
    
    metrics = {
        'test_mae': mean_absolute_error(y_test, y_pred_test_rounded),
        'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
        'test_r2': r2_score(y_test, y_pred_test),
        'train_mae': mean_absolute_error(y_train, y_pred_train_rounded),
        'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
        'train_r2': r2_score(y_train, y_pred_train),
        'model_type': model_type,
        'n_features': len(available_features),
        'feature_cols': available_features,
        'orders_per_waiter': 12,
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test)
    }
    
    if verbose:
        print("МЕТРИКИ МОДЕЛИ")
        print(f"Тип: {metrics['model_type']}")
        print(f"MAE (Test): {metrics['test_mae']:.2f}")
        print(f"RMSE (Test): {metrics['test_rmse']:.2f}")
        print(f"R2 (Test): {metrics['test_r2']:.3f}")
        print(f"MAE (Train): {metrics['train_mae']:.2f}")
        print(f"R2 (Train): {metrics['train_r2']:.3f}")
        
        if hasattr(model, 'feature_importances_'):
            print("\nВажность признаков (топ-10):")
            imp = pd.DataFrame({
                'feature': available_features,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)
            for _, row in imp.head(10).iterrows():
                print(f"   {row['feature']}: {row['importance']:.3f}")
    
    if model_path:
        model_dir = os.path.dirname(model_path)
        if model_dir and not os.path.exists(model_dir):
            os.makedirs(model_dir)
        
        model_data = {
            'model': model,
            'feature_cols': available_features,
            'metrics': metrics,
            'orders_per_waiter': 12
        }
        
        joblib.dump(model_data, model_path)
        
        if verbose:
            print(f"\nМодель сохранена: {os.path.abspath(model_path)}")
    
    return model, metrics