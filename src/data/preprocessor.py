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
        
        if 'temperature_mean' in df_agg.columns:
            print(f"\nСтатистика погоды:")
            print(f"  Температура: {df_agg['temperature_mean'].mean():.1f}°")
            print(f"  Осадки: {df_agg['precipitation'].mean():.2f} мм/день")
    
    return df_agg, FEATURE_COLS


def _generate_features(df_agg: pd.DataFrame) -> pd.DataFrame:
    df_agg['hour'] = df_agg['datetime'].dt.hour
    df_agg['hour_encoded'] = np.sin(2 * np.pi * df_agg['hour'] / 24)
    df_agg['hour_encoded_cos'] = np.cos(2 * np.pi * df_agg['hour'] / 24)
    
    # Пиковые часы
    df_agg['is_lunch_peak'] = ((df_agg['hour'] >= 12) & (df_agg['hour'] <= 14)).astype(int)
    df_agg['is_dinner_peak'] = ((df_agg['hour'] >= 18) & (df_agg['hour'] <= 21)).astype(int)
    df_agg['is_peak_hour'] = (df_agg['is_lunch_peak'] | df_agg['is_dinner_peak']).astype(int)
    
    # Календарь
    df_agg['day_of_week'] = df_agg['datetime'].dt.weekday
    df_agg['month'] = df_agg['datetime'].dt.month
    df_agg['day_of_month'] = df_agg['datetime'].dt.day
    df_agg['week_of_month'] = (df_agg['day_of_month'] - 1) // 7 + 1
    df_agg['week_of_year'] = df_agg['datetime'].dt.isocalendar().week.astype(int)
    df_agg['quarter'] = df_agg['datetime'].dt.quarter
    df_agg['is_weekend'] = (df_agg['day_of_week'] >= 5).astype(int)
    df_agg['is_month_start'] = df_agg['datetime'].dt.is_month_start.astype(int)
    df_agg['is_month_end'] = df_agg['datetime'].dt.is_month_end.astype(int)
    df_agg['is_quarter_start'] = df_agg['datetime'].dt.is_quarter_start.astype(int)
    df_agg['is_quarter_end'] = df_agg['datetime'].dt.is_quarter_end.astype(int)
    
    # Праздники России
    df_agg['is_holiday'] = df_agg['datetime'].dt.date.apply(
        lambda x: 1 if x in ru_holidays else 0
    )
    
    # Специальные даты и события
    df_agg['is_valentine'] = ((df_agg['month'] == 2) & (df_agg['day_of_month'] == 14)).astype(int)
    df_agg['is_new_year_week'] = ((df_agg['month'] == 1) & (df_agg['day_of_month'] <= 7)).astype(int)
    df_agg['is_march_8'] = ((df_agg['month'] == 3) & (df_agg['day_of_month'] >= 7) & (df_agg['day_of_month'] <= 9)).astype(int)
    df_agg['is_may_holidays'] = ((df_agg['month'] == 5) & (df_agg['day_of_month'] >= 1) & (df_agg['day_of_month'] <= 10)).astype(int)
    df_agg['is_june_holiday'] = ((df_agg['month'] == 6) & (df_agg['day_of_month'] >= 11) & (df_agg['day_of_month'] <= 14)).astype(int)
    df_agg['is_november_holiday'] = ((df_agg['month'] == 11) & (df_agg['day_of_month'] >= 3) & (df_agg['day_of_month'] <= 5)).astype(int)
    df_agg['is_december_holidays'] = ((df_agg['month'] == 12) & (df_agg['day_of_month'] >= 30)).astype(int)
    
    # Сезонность
    df_agg['is_winter'] = df_agg['month'].isin([12, 1, 2]).astype(int)
    df_agg['is_spring'] = df_agg['month'].isin([3, 4, 5]).astype(int)
    df_agg['is_summer'] = df_agg['month'].isin([6, 7, 8]).astype(int)
    df_agg['is_autumn'] = df_agg['month'].isin([9, 10, 11]).astype(int)
    
    # Взаимодействия времени и календаря
    df_agg['hour_weekend'] = df_agg['hour_encoded'] * df_agg['is_weekend']
    df_agg['hour_holiday'] = df_agg['hour_encoded'] * df_agg['is_holiday']
    df_agg['peak_weekend'] = df_agg['is_peak_hour'] * df_agg['is_weekend']
    df_agg['peak_holiday'] = df_agg['is_peak_hour'] * df_agg['is_holiday']
    
    # Конкретные дни × ужин
    df_agg['friday_dinner'] = ((df_agg['day_of_week'] == 4) & df_agg['is_dinner_peak']).astype(int)
    df_agg['saturday_dinner'] = ((df_agg['day_of_week'] == 5) & df_agg['is_dinner_peak']).astype(int)
    df_agg['sunday_dinner'] = ((df_agg['day_of_week'] == 6) & df_agg['is_dinner_peak']).astype(int)
    df_agg['saturday_lunch'] = ((df_agg['day_of_week'] == 5) & df_agg['is_lunch_peak']).astype(int)
    df_agg['sunday_lunch'] = ((df_agg['day_of_week'] == 6) & df_agg['is_lunch_peak']).astype(int)
    
    # Лаговые признаки (расширенные)
    df_agg['lag_orders_1h'] = df_agg['orders_count'].shift(1)
    df_agg['lag_orders_2h'] = df_agg['orders_count'].shift(2)
    df_agg['lag_orders_3h'] = df_agg['orders_count'].shift(3)
    df_agg['lag_orders_24h'] = df_agg['orders_count'].shift(24)
    df_agg['lag_orders_48h'] = df_agg['orders_count'].shift(48)
    df_agg['lag_orders_168h'] = df_agg['orders_count'].shift(168)
    df_agg['lag_orders_336h'] = df_agg['orders_count'].shift(336)
    
    # Лаги для гостей
    df_agg['lag_guests_1h'] = df_agg['guests_count'].shift(1)
    df_agg['lag_guests_24h'] = df_agg['guests_count'].shift(24)
    df_agg['lag_guests_168h'] = df_agg['guests_count'].shift(168)
    
    # Скользящие средние (расширенные)
    df_agg['rolling_mean_3h'] = df_agg['orders_count'].rolling(3, min_periods=1).mean()
    df_agg['rolling_mean_6h'] = df_agg['orders_count'].rolling(6, min_periods=1).mean()
    df_agg['rolling_mean_12h'] = df_agg['orders_count'].rolling(12, min_periods=1).mean()
    df_agg['rolling_mean_24h'] = df_agg['orders_count'].rolling(24, min_periods=1).mean()
    df_agg['rolling_mean_168h'] = df_agg['orders_count'].rolling(168, min_periods=1).mean()
    
    df_agg['rolling_std_3h'] = df_agg['orders_count'].rolling(3, min_periods=1).std()
    df_agg['rolling_std_24h'] = df_agg['orders_count'].rolling(24, min_periods=1).std()
    df_agg['rolling_std_168h'] = df_agg['orders_count'].rolling(168, min_periods=1).std()
    
    # Скользящие максимумы
    df_agg['rolling_max_24h'] = df_agg['orders_count'].rolling(24, min_periods=1).max()
    df_agg['rolling_max_168h'] = df_agg['orders_count'].rolling(168, min_periods=1).max()
    df_agg['rolling_max_720h'] = df_agg['orders_count'].rolling(720, min_periods=1).max()
    
    # Отклонение от среднего
    df_agg['deviation_from_mean_24h'] = df_agg['orders_count'] - df_agg['rolling_mean_24h']
    df_agg['deviation_from_mean_168h'] = df_agg['orders_count'] - df_agg['rolling_mean_168h']
    
    # Процентильные признаки
    df_agg['is_high_demand'] = (df_agg['orders_count'] > df_agg['orders_count'].quantile(0.75)).astype(int)
    df_agg['is_very_high_demand'] = (df_agg['orders_count'] > df_agg['orders_count'].quantile(0.90)).astype(int)
    
    # Тренд
    df_agg['trend'] = np.arange(len(df_agg))
    
    # Погодные признаки
    weather_cols = ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']
    for col in weather_cols:
        if col in df_agg.columns:
            if df_agg[col].notna().any():
                df_agg[col] = df_agg[col].fillna(df_agg[col].median())
            else:
                df_agg[col] = 0
        else:
            df_agg[col] = 0
    
    # Взаимодействия с погодой
    if 'is_peak_hour' in df_agg.columns:
        df_agg['rainy_peak'] = df_agg['is_rainy'] * df_agg['is_peak_hour']
        df_agg['extreme_peak'] = df_agg['is_extreme_weather'] * df_agg['is_peak_hour']
        df_agg['cold_weekend'] = df_agg['is_weekend'] * (df_agg['temperature_mean'] < 0).astype(int)
        df_agg['warm_weekend'] = df_agg['is_weekend'] * (df_agg['temperature_mean'] > 15).astype(int)
    else:
        df_agg['rainy_peak'] = 0
        df_agg['extreme_peak'] = 0
        df_agg['cold_weekend'] = 0
        df_agg['warm_weekend'] = 0
    
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
            'guests_count': 0,
        })
        current += timedelta(hours=1)
    
    df_future = pd.DataFrame(future_hours)
    
    # Удаляем дубликаты из истории
    hist_df = hist_df.drop_duplicates(subset=['datetime'], keep='last').copy()
    
    df_combined = pd.concat([hist_df, df_future], ignore_index=True)
    
    # Сортируем и удаляем дубликаты
    df_combined = df_combined.sort_values('datetime').reset_index(drop=True)
    df_combined = df_combined.drop_duplicates(subset=['datetime'], keep='last')
    
    df_combined['orders_count'] = df_combined['orders_count'].astype(float)
    df_combined['guests_count'] = df_combined['guests_count'].astype(float)
    
    future_mask = df_combined['datetime'] >= from_datetime
    
    hist_df_copy = hist_df.copy()
    hist_df_copy['hour'] = hist_df_copy['datetime'].dt.hour
    
    hour_medians = hist_df_copy.groupby('hour')['orders_count'].median()
    hour_medians_guests = hist_df_copy.groupby('hour')['guests_count'].median()
    
    max_allowed = hist_df_copy['orders_count'].max()
    max_allowed_guests = hist_df_copy['guests_count'].max()
    
    df_combined.loc[future_mask, 'orders_count'] = df_combined.loc[
        future_mask, 'datetime'
    ].dt.hour.map(hour_medians).clip(upper=max_allowed)
    
    df_combined.loc[future_mask, 'guests_count'] = df_combined.loc[
        future_mask, 'datetime'
    ].dt.hour.map(hour_medians_guests).clip(upper=max_allowed_guests)
    
    df_combined = _generate_features(df_combined)
    
    global_median = hist_df['orders_count'].median()
    lag_cols = ['lag_orders_1h', 'lag_orders_2h', 'lag_orders_3h', 'lag_orders_24h', 
                'lag_orders_48h', 'lag_orders_168h', 'lag_orders_336h',
                'rolling_mean_3h', 'rolling_mean_6h', 'rolling_mean_12h', 
                'rolling_mean_24h', 'rolling_mean_168h',
                'rolling_std_3h', 'rolling_std_24h', 'rolling_std_168h',
                'rolling_max_24h', 'rolling_max_168h', 'rolling_max_720h',
                'lag_guests_1h', 'lag_guests_24h', 'lag_guests_168h']
    
    for col in lag_cols:
        if col in df_combined.columns:
            df_combined.loc[future_mask & (df_combined[col] == 0), col] = global_median
    
    df_combined = df_combined.fillna(0)
    
    df_pred = df_combined[df_combined['datetime'] >= from_datetime].copy()
    df_pred = df_pred[df_pred['datetime'] <= to_datetime].copy()
    
    # Удаляем дубликаты перед возвратом
    df_pred = df_pred.drop_duplicates(subset=['datetime'], keep='last').reset_index(drop=True)
    
    missing_cols = set(feature_cols) - set(df_pred.columns)
    if missing_cols:
        if verbose:
            print(f"  Добавляю отсутствующие признаки: {missing_cols}")
        for col in missing_cols:
            df_pred[col] = 0
    
    if verbose:
        print(f"Часов в прогнозе: {len(df_pred)}")
        print(f"Медиана историческая заказов/час: {global_median:.2f}")
        print(f"Среднее в прогнозе (до модели): {df_pred['orders_count'].mean():.2f}")
    
    return df_pred, df_combined