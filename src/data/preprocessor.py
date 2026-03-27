import pandas as pd
import numpy as np
import holidays
from typing import Tuple, List
from src.config import FEATURE_COLS, TARGET_COLUMN

ru_holidays = holidays.Russia()


def prepare_features(df: pd.DataFrame, verbose: bool = True) -> Tuple[pd.DataFrame, List]:
    df = df.copy()
    
    if verbose:
        print(f"\nВходные данные: {len(df)} записей")
        print(f"Колонки: {list(df.columns)}")
    
    # Проверяем datetime
    if 'datetime' not in df.columns:
        if 'order_datetime' in df.columns:
            df.rename(columns={'order_datetime': 'datetime'}, inplace=True)
        else:
            raise ValueError("Колонка 'datetime' не найдена!")
    
    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
    df = df.dropna(subset=['datetime'])
    
    if verbose:
        print(f"\nКорректных дат: {len(df)} из {len(df)}")
        print(f"Диапазон: {df['datetime'].min()} — {df['datetime'].max()}")
    
    # Целевые переменные
    if TARGET_COLUMN not in df.columns:
        if 'orders_count' in df.columns:
            df[TARGET_COLUMN] = df['orders_count']
        else:
            raise ValueError("Целевая переменная orders_count не найдена!")
    
    if 'guests_count' not in df.columns:
        raise ValueError("Колонка 'guests_count' не найдена!")
    
    df_agg = _generate_features(df)
    
    if verbose:
        print(f"Сгенерировано {len(FEATURE_COLS)} признаков")
        print(f"Статистика целевой переменной (заказы):")
        print(df_agg[TARGET_COLUMN].describe())
        print(f"\nСтатистика целевой переменной (гости):")
        print(df_agg['guests_count'].describe())
    
    return df_agg, FEATURE_COLS


def _generate_features(df_agg: pd.DataFrame) -> pd.DataFrame:
    df_agg['hour'] = df_agg['datetime'].dt.hour
    df_agg['hour_encoded'] = np.sin(2 * np.pi * df_agg['hour'] / 24)
    
    # Пиковые часы
    df_agg['is_lunch_peak'] = ((df_agg['hour'] >= 12) & (df_agg['hour'] <= 14)).astype(int)
    df_agg['is_dinner_peak'] = ((df_agg['hour'] >= 18) & (df_agg['hour'] <= 21)).astype(int)
    df_agg['is_peak_hour'] = (df_agg['is_lunch_peak'] | df_agg['is_dinner_peak']).astype(int)
    
    # Календарь
    df_agg['day_of_week'] = df_agg['datetime'].dt.weekday
    df_agg['month'] = df_agg['datetime'].dt.month
    df_agg['day_of_month'] = df_agg['datetime'].dt.day
    df_agg['is_weekend'] = (df_agg['day_of_week'] >= 5).astype(int)
    df_agg['is_month_start'] = df_agg['datetime'].dt.is_month_start.astype(int)
    df_agg['is_month_end'] = df_agg['datetime'].dt.is_month_end.astype(int)
    
    # Праздники
    df_agg['is_holiday'] = df_agg['datetime'].dt.date.apply(
        lambda x: 1 if x in ru_holidays else 0
    )
    
    # Взаимодействия
    df_agg['hour_weekend'] = df_agg['hour_encoded'] * df_agg['is_weekend']
    df_agg['hour_holiday'] = df_agg['hour_encoded'] * df_agg['is_holiday']
    df_agg['peak_weekend'] = df_agg['is_peak_hour'] * df_agg['is_weekend']
    df_agg['peak_holiday'] = df_agg['is_peak_hour'] * df_agg['is_holiday']
    
    # Конкретные дни × ужин
    df_agg['friday_dinner'] = ((df_agg['day_of_week'] == 4) & df_agg['is_dinner_peak']).astype(int)
    df_agg['saturday_dinner'] = ((df_agg['day_of_week'] == 5) & df_agg['is_dinner_peak']).astype(int)
    df_agg['sunday_dinner'] = ((df_agg['day_of_week'] == 6) & df_agg['is_dinner_peak']).astype(int)
    
    # Лаговые признаки
    df_agg['lag_orders_1h'] = df_agg['orders_count'].shift(1)
    df_agg['lag_orders_24h'] = df_agg['orders_count'].shift(24)
    df_agg['lag_orders_168h'] = df_agg['orders_count'].shift(168)
    
    # Скользящие средние
    df_agg['rolling_mean_3h'] = df_agg['orders_count'].rolling(3, min_periods=1).mean()
    df_agg['rolling_mean_24h'] = df_agg['orders_count'].rolling(24, min_periods=1).mean()
    df_agg['rolling_std_24h'] = df_agg['orders_count'].rolling(24, min_periods=1).std()
    
    # Погодные признаки (если есть)
    weather_cols = ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']
    for col in weather_cols:
        if col in df_agg.columns:
            df_agg[col] = df_agg[col].fillna(df_agg[col].median() if df_agg[col].notna().any() else 0)
        else:
            df_agg[col] = 0
    
    # Взаимодействия с погодой
    df_agg['rainy_peak'] = df_agg.get('is_rainy', 0) * df_agg['is_peak_hour']
    df_agg['extreme_peak'] = df_agg.get('is_extreme_weather', 0) * df_agg['is_peak_hour']
    
    df_agg = df_agg.fillna(0)
    
    return df_agg


def prepare_for_prediction(
    hist_df: pd.DataFrame,
    from_datetime: pd.Timestamp,
    to_datetime: pd.Timestamp,
    feature_cols: List,
    verbose: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    from datetime import timedelta
    
    future_hours = []
    current = from_datetime
    
    while current <= to_datetime:
        future_hours.append({
            'datetime': current,
            'orders_count': 0,
        })
        current += timedelta(hours=1)
    
    df_future = pd.DataFrame(future_hours)
    
    df_combined = pd.concat([hist_df, df_future], ignore_index=True)
    df_combined = df_combined.sort_values('datetime').reset_index(drop=True)
    
    # Конвертируем orders_count в float
    df_combined['orders_count'] = df_combined['orders_count'].astype(float)
    
    # Заполняем будущие часы МЕДИАНОЙ по часу суток (меньше выбросов)
    future_mask = df_combined['datetime'] >= from_datetime
    
    hist_df_copy = hist_df.copy()
    hist_df_copy['hour'] = hist_df_copy['datetime'].dt.hour
    
    # Используем медиану вместо среднего
    hour_medians = hist_df_copy.groupby('hour')['orders_count'].median()
    
    # Ограничиваем максимум (не больше 50% от исторического максимума)
    max_allowed = hist_df_copy['orders_count'].max() * 0.5
    
    df_combined.loc[future_mask, 'orders_count'] = df_combined.loc[
        future_mask, 'datetime'
    ].dt.hour.map(hour_medians).clip(upper=max_allowed)
    
    df_combined = _generate_features(df_combined)
    
    # Заполняем лаги медианой
    global_median = hist_df['orders_count'].median()
    lag_cols = ['lag_orders_1h', 'lag_orders_24h', 'lag_orders_168h', 
                'rolling_mean_3h', 'rolling_mean_24h', 'rolling_std_24h']
    
    for col in lag_cols:
        if col in df_combined.columns:
            df_combined.loc[future_mask & (df_combined[col] == 0), col] = global_median
    
    df_combined = df_combined.fillna(0)
    
    df_pred = df_combined[df_combined['datetime'] >= from_datetime].copy()
    df_pred = df_pred[df_pred['datetime'] <= to_datetime].copy()
    
    missing_cols = set(feature_cols) - set(df_pred.columns)
    if missing_cols:
        raise ValueError(f"Отсутствуют признаки: {missing_cols}")
    
    if verbose:
        print(f"Часов в прогнозе: {len(df_pred)}")
        print(f"Медиана историческая заказов/час: {global_median:.2f}")
        print(f"Среднее в прогнозе (до модели): {df_pred['orders_count'].mean():.2f}")
    
    return df_pred, df_combined