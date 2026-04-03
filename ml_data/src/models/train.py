import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
from typing import Tuple, Dict, Optional
import warnings
import os
from pathlib import Path
from src.config import (
    MODEL_PARAMS, TEST_SIZE, RANDOM_STATE,
    TARGET_COLUMN, MODEL_FILE
)

warnings.filterwarnings('ignore')

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor


def train(
    df_agg: pd.DataFrame,
    feature_cols: list,
    model_type: str = 'xgboost',
    test_size: float = None,
    random_state: int = None,
    model_path: str = None,
    verbose: bool = True,
    existing_model_path: str = None,
    incremental: bool = False
) -> Tuple[object, Dict]:
    test_size = test_size or TEST_SIZE
    random_state = random_state or RANDOM_STATE
    
    if verbose:
        print("ОБУЧЕНИЕ МОДЕЛИ")
        print(f"Всего записей в df_agg: {len(df_agg)}")
        print(f"Тип модели: {model_type}")
        if incremental and existing_model_path:
            print(f"Режим: дообучение существующей модели")
    
    # Проверка данных
    if len(df_agg) < 100:
        raise ValueError(f"Слишком мало данных: {len(df_agg)}. Минимум 100.")
    
    # Проверка целевой переменной
    if TARGET_COLUMN not in df_agg.columns:
        raise ValueError(f"Целевая переменная '{TARGET_COLUMN}' не найдена.")
    
    # Проверка признаков
    available_features = [col for col in feature_cols if col in df_agg.columns]
    if len(available_features) == 0:
        raise ValueError(f"Ни один признак не найден.")
    
    if verbose:
        print(f"Используемые признаки: {len(available_features)}")
    
    # Рассчитать коэффициент гостей на заказ
    if 'guests_count' in df_agg.columns and 'orders_count' in df_agg.columns:
        total_orders = df_agg['orders_count'].sum()
        total_guests = df_agg['guests_count'].sum()
        avg_guests_per_order = total_guests / max(total_orders, 1)
    else:
        avg_guests_per_order = 2.03
    
    if verbose:
        print(f"Среднее гостей на заказ: {avg_guests_per_order:.2f}")
    
    X = df_agg[available_features]
    y = df_agg[TARGET_COLUMN]
    
    # Проверка на NaN
    if X.isnull().any().any():
        X = X.fillna(0)
    
    if y.isnull().any():
        y = y.fillna(y.median())
    
    # Разделение
    split_idx = int(len(df_agg) * (1 - test_size))
    
    if verbose:
        print(f"Разделение: всего={len(df_agg)}, train={split_idx}, test={len(df_agg) - split_idx}")
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    if verbose:
        print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Загрузка существующей модели для дообучения
    existing_model = None
    if incremental and existing_model_path and os.path.exists(existing_model_path):
        if verbose:
            print(f"Загрузка существующей модели: {existing_model_path}")
        model_data = joblib.load(existing_model_path)
        existing_model = model_data['model']
    
    # Создание модели
    if model_type == 'xgboost':
        if not XGB_AVAILABLE:
            print("XGBoost не установлен, используется GradientBoosting")
            model_type = 'gradient_boosting'
        else:
            params = MODEL_PARAMS.get('xgboost', {
                'n_estimators': 1000,
                'max_depth': 6,
                'learning_rate': 0.01,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': random_state,
                'n_jobs': -1
            })
            if existing_model is not None and incremental:
                # Дообучение XGBoost
                model = existing_model
                model.fit(X_train, y_train, xgb_model=model)
                if verbose:
                    print(f"Дообучение XGBoost...")
            else:
                model = xgb.XGBRegressor(**params)
                if verbose:
                    print(f"Обучение XGBoost...")
                model.fit(X_train, y_train)
    
    elif model_type == 'random_forest':
        params = MODEL_PARAMS.get('random_forest', {})
        model = RandomForestRegressor(**params)
        if verbose:
            print(f"Обучение RandomForest...")
        model.fit(X_train, y_train)
    
    elif model_type == 'gradient_boosting':
        params = MODEL_PARAMS.get('gradient_boosting', {})
        model = GradientBoostingRegressor(**params)
        if verbose:
            print(f"Обучение GradientBoosting...")
        model.fit(X_train, y_train)
    
    else:
        raise ValueError(f"Неизвестный тип модели: {model_type}")
    
    # Предсказания
    y_pred_test = model.predict(X_test)
    y_pred_test_rounded = np.maximum(0, np.round(y_pred_test)).astype(int)
    
    y_pred_train = model.predict(X_train)
    y_pred_train_rounded = np.maximum(0, np.round(y_pred_train)).astype(int)
    
    # Метрики
    metrics = {
        'test_mae': float(mean_absolute_error(y_test, y_pred_test_rounded)),
        'test_rmse': float(np.sqrt(mean_squared_error(y_test, y_pred_test))),
        'test_r2': float(r2_score(y_test, y_pred_test)),
        'train_mae': float(mean_absolute_error(y_train, y_pred_train_rounded)),
        'train_rmse': float(np.sqrt(mean_squared_error(y_train, y_pred_train))),
        'train_r2': float(r2_score(y_train, y_pred_train)),
        'model_type': model_type,
        'n_features': len(available_features),
        'feature_cols': available_features,
        'target_column': TARGET_COLUMN,
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test),
        'training_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'incremental': incremental
    }
    
    if verbose:
        print("\nМЕТРИКИ МОДЕЛИ")
        print(f"Тип: {metrics['model_type']}")
        print(f"MAE (Test): {metrics['test_mae']:.2f}")
        print(f"RMSE (Test): {metrics['test_rmse']:.2f}")
        print(f"R² (Test): {metrics['test_r2']:.3f}")
        print(f"MAE (Train): {metrics['train_mae']:.2f}")
        print(f"R² (Train): {metrics['train_r2']:.3f}")
        
        if hasattr(model, 'feature_importances_'):
            print("\nВажность признаков (топ-10):")
            imp = pd.DataFrame({
                'feature': available_features,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)
            for _, row in imp.head(10).iterrows():
                print(f"   {row['feature']}: {row['importance']:.3f}")
    
    # Сохранение модели
    if model_path:
        model_dir = os.path.dirname(model_path)
        if model_dir and not os.path.exists(model_dir):
            os.makedirs(model_dir)
        
        model_data = {
            'model': model,
            'feature_cols': available_features,
            'metrics': metrics,
            'avg_guests_per_order': avg_guests_per_order,
            'target_column': TARGET_COLUMN,
            'training_data_info': {
                'n_samples': len(df_agg),
                'date_range': {
                    'min': str(df_agg['datetime'].min()) if 'datetime' in df_agg.columns else None,
                    'max': str(df_agg['datetime'].max()) if 'datetime' in df_agg.columns else None
                }
            }
        }
        
        joblib.dump(model_data, model_path)
        
        if verbose:
            print(f"\nМодель сохранена: {os.path.abspath(model_path)}")
    
    return model, metrics


def update_model(
    new_data: pd.DataFrame,
    feature_cols: list,
    model_path: str,
    existing_model_path: str,
    model_type: str = 'xgboost',
    verbose: bool = True
) -> Tuple[object, Dict]:
    if verbose:
        print("\nДООБУЧЕНИЕ МОДЕЛИ")
        print(f"Новых записей: {len(new_data)}")
    
    return train(
        df_agg=new_data,
        feature_cols=feature_cols,
        model_type=model_type,
        model_path=model_path,
        existing_model_path=existing_model_path,
        incremental=True,
        verbose=verbose
    )