import pandas as pd
import numpy as np
import joblib
from typing import Optional, Union
from datetime import datetime, timedelta
import os
from pathlib import Path
from src.config import (
    MODEL_FILE, RAW_DATA_FILE,
    WORKING_HOUR_START, WORKING_HOUR_END,
    MIN_ORDERS_PER_HOUR, MIN_GUESTS_PER_HOUR,
    AVG_GUESTS_PER_ORDER,
    WEATHER_LATITUDE, WEATHER_LONGITUDE
)
from src.data.loader import load_raw_dataset
from src.data.preprocessor import prepare_for_prediction, prepare_features
from src.data.weather_parser import WeatherParser, merge_weather_with_orders


def predict(
    model_path: str = None,
    raw_data_path: str = None,
    from_datetime: Optional[Union[str, datetime]] = None,
    to_datetime: Optional[Union[str, datetime]] = None,
    hours_ahead: int = 168,
    verbose: bool = True,
    force_fresh_weather: bool = True
) -> pd.DataFrame:
    model_path = model_path or str(MODEL_FILE)
    raw_data_path = raw_data_path or str(RAW_DATA_FILE)
    
    if verbose:
        print("ПРОГНОЗ КОЛИЧЕСТВА ЗАКАЗОВ И ГОСТЕЙ")
        print("Используется: 1 модель + конверсия гостей + свежая погода")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Модель не найдена: {model_path}")
    
    model_data = joblib.load(model_path)
    model = model_data['model']
    feature_cols = model_data['feature_cols']
    
    avg_guests = model_data.get('avg_guests_per_order', AVG_GUESTS_PER_ORDER)
    
    if verbose:
        print(f"Модель: {model_data['metrics']['model_type']}")
        print(f"Признаков: {len(feature_cols)}")
        print(f"Среднее гостей на заказ: {avg_guests:.2f}")
        if 'training_date' in model_data.get('metrics', {}):
            print(f"Дата обучения модели: {model_data['metrics']['training_date']}")
    
    df = load_raw_dataset(raw_data_path)
    df = _clean_for_predict(df)
    
    hist_agg, _ = prepare_features(df, verbose=False)
    last_hist_datetime = hist_agg['datetime'].max()
    
    if verbose:
        print(f"История: {hist_agg['datetime'].min()} — {last_hist_datetime}")
    
    if from_datetime is None and to_datetime is None:
        from_datetime = last_hist_datetime + pd.Timedelta(hours=1)
        to_datetime = from_datetime + pd.Timedelta(hours=hours_ahead - 1)
    else:
        if isinstance(from_datetime, str):
            from_datetime = pd.to_datetime(from_datetime)
        if isinstance(to_datetime, str):
            to_datetime = pd.to_datetime(to_datetime)
        
        if to_datetime is None:
            to_datetime = from_datetime + pd.Timedelta(hours=hours_ahead - 1)
    
    if verbose:
        print(f"Прогноз: {from_datetime} — {to_datetime}")
    
    df_pred, _ = prepare_for_prediction(
        hist_agg,
        from_datetime,
        to_datetime,
        feature_cols,
        verbose=verbose
    )
    
    _add_weather_to_forecast(
        df_pred, 
        from_datetime, 
        to_datetime, 
        verbose, 
        force_fresh=force_fresh_weather
    )
    
    missing_features = set(feature_cols) - set(df_pred.columns)
    if missing_features:
        if verbose:
            print(f"  Добавляю отсутствующие признаки: {missing_features}")
        for col in missing_features:
            df_pred[col] = 0
    
    X_pred = df_pred[feature_cols]
    predictions_orders = model.predict(X_pred)
    df_pred['orders_predicted'] = np.maximum(0, np.round(predictions_orders)).astype(int)
    
    df_pred['guests_predicted'] = (df_pred['orders_predicted'] * avg_guests).round().astype(int)
    
    df_pred['orders_with_buffer'] = (df_pred['orders_predicted'] * 1.50).astype(int)
    df_pred['guests_with_buffer'] = (df_pred['guests_predicted'] * 1.50).astype(int)
    
    # Дополнительное увеличение для пиковых часов
    peak_mask = df_pred['is_peak_hour'] == 1
    weekend_mask = df_pred['is_weekend'] == 1

    # Для пиковых часов в выходные — ещё +20%
    df_pred.loc[peak_mask & weekend_mask, 'orders_with_buffer'] = (
        df_pred.loc[peak_mask & weekend_mask, 'orders_with_buffer'] * 1.20
    ).astype(int)

    df_pred.loc[peak_mask & weekend_mask, 'guests_with_buffer'] = (
        df_pred.loc[peak_mask & weekend_mask, 'guests_with_buffer'] * 1.20
    ).astype(int)
    
    night_hours_mask = (df_pred['hour'] < WORKING_HOUR_START) | (df_pred['hour'] >= WORKING_HOUR_END)
    
    df_pred.loc[night_hours_mask, 'orders_predicted'] = 0
    df_pred.loc[night_hours_mask, 'guests_predicted'] = 0
    df_pred.loc[night_hours_mask, 'orders_with_buffer'] = 0
    df_pred.loc[night_hours_mask, 'guests_with_buffer'] = 0
    
    working_hours_mask = ~night_hours_mask
    
    df_pred.loc[working_hours_mask, 'orders_predicted'] = df_pred.loc[
        working_hours_mask, 'orders_predicted'
    ].clip(lower=MIN_ORDERS_PER_HOUR)
    
    df_pred.loc[working_hours_mask, 'guests_predicted'] = df_pred.loc[
        working_hours_mask, 'guests_predicted'
    ].clip(lower=MIN_GUESTS_PER_HOUR)
    
    df_pred.loc[working_hours_mask, 'orders_with_buffer'] = df_pred.loc[
        working_hours_mask, 'orders_with_buffer'
    ].clip(lower=MIN_ORDERS_PER_HOUR)
    
    df_pred.loc[working_hours_mask, 'guests_with_buffer'] = df_pred.loc[
        working_hours_mask, 'guests_with_buffer'
    ].clip(lower=MIN_GUESTS_PER_HOUR)
    
    if verbose:
        _print_forecast_report(df_pred)
    
    return df_pred[['datetime', 'hour', 'day_of_week', 'is_peak_hour',
                    'is_weekend', 'is_holiday',
                    'orders_predicted', 'orders_with_buffer',
                    'guests_predicted', 'guests_with_buffer',
                    'lag_orders_1h', 'lag_orders_24h', 'rolling_mean_24h']]


def _add_weather_to_forecast(
    df_pred: pd.DataFrame,
    from_datetime: pd.Timestamp,
    to_datetime: pd.Timestamp,
    verbose: bool = True,
    force_fresh: bool = True
) -> None:
    try:
        if verbose:
            print("Загрузка погоды для периода прогноза...")
            if force_fresh:
                print("  (свежий запрос, кэш игнорируется)")
        
        weather_parser = WeatherParser(
            latitude=WEATHER_LATITUDE,
            longitude=WEATHER_LONGITUDE
        )
        
        forecast_start = from_datetime.strftime('%Y-%m-%d')
        forecast_end = to_datetime.strftime('%Y-%m-%d')
        
        weather_forecast = weather_parser.get_weather_for_date_range(
            start_date=forecast_start,
            end_date=forecast_end,
            verbose=False,
            use_cache=not force_fresh
        )
        
        if weather_forecast is not None and len(weather_forecast) > 0:
            weather_forecast = weather_forecast.copy()
            weather_forecast['datetime'] = pd.to_datetime(weather_forecast['date']).dt.floor('h')
            
            df_pred.merge(
                weather_forecast.drop(columns=['date'], errors='ignore'),
                on='datetime',
                how='left',
                inplace=True
            )
            
            weather_cols = ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']
            for col in weather_cols:
                if col in df_pred.columns and df_pred[col].isna().any():
                    if df_pred[col].notna().any():
                        df_pred[col] = df_pred[col].fillna(df_pred[col].median())
                    else:
                        df_pred[col] = 0
            
            if 'is_peak_hour' in df_pred.columns:
                df_pred['rainy_peak'] = df_pred['is_rainy'] * df_pred['is_peak_hour']
                df_pred['extreme_peak'] = df_pred['is_extreme_weather'] * df_pred['is_peak_hour']
            
            if verbose:
                print(f"  Погода добавлена: {weather_forecast['date'].nunique()} дней")
        else:
            _add_zero_weather_columns(df_pred)
            if verbose:
                print("  Нет данных о погоде — использую нулевые значения")
                
    except ImportError:
        _add_zero_weather_columns(df_pred)
        if verbose:
            print("  Модуль weather_parser не найден — пропускаю погоду")
    except Exception as e:
        _add_zero_weather_columns(df_pred)
        if verbose:
            print(f"  Ошибка при загрузке погоды: {type(e).__name__} — продолжаю без погоды")


def _add_zero_weather_columns(df: pd.DataFrame) -> None:
    weather_cols = [
        'temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather',
        'rainy_peak', 'extreme_peak'
    ]
    for col in weather_cols:
        if col not in df.columns:
            df[col] = 0


def _clean_for_predict(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    mapping = {
        'Отделение': 'department',
        'Учетный день': 'account_date',
        'Номер чека': 'check_number',
        'Время открытия': 'open_time',
        'Время закрытия': 'close_time',
        'Заказов': 'orders',
        'Количество гостей': 'guests_count'
    }
    df = df.rename(columns=mapping)
    
    if 'order_datetime' not in df.columns:
        for col in ['open_time', 'account_date']:
            if col in df.columns:
                df['order_datetime'] = pd.to_datetime(df[col], errors='coerce')
                if df['order_datetime'].notna().sum() > 0:
                    break
    
    if 'order_id' not in df.columns:
        if 'check_number' in df.columns:
            df['order_id'] = df['check_number']
        else:
            df['order_id'] = range(len(df))
    
    if 'total_bill' not in df.columns:
        df['total_bill'] = 0
    
    if 'items_count' not in df.columns:
        df['items_count'] = 1
    
    if 'order_datetime' in df.columns:
        df = df.dropna(subset=['order_datetime'])
    
    return df


def _print_forecast_report(df_pred: pd.DataFrame):
    print("\nПРОГНОЗ ПО ЧАСАМ")
    print(f"{'Дата-время':<20} {'Час':<5} {'День':<5} {'Пик':<4} {'Заказов':<9} {'Гостей':<10}")
    
    day_names = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}
    
    for _, row in df_pred.head(24).iterrows():
        dt_str = row['datetime'].strftime('%Y-%m-%d %H:00')
        day_name = day_names.get(row['day_of_week'], '')
        peak = '1' if row['is_peak_hour'] else '0'
        # ← Используем buffer
        print(f"{dt_str:<20} {row['hour']:<5} {day_name:<5} {peak:<4} {row['orders_with_buffer']:<9} {row['guests_with_buffer']:<10}")
    
    print(f"\nВсего часов прогноза: {len(df_pred)}")
    # ← Используем buffer
    print(f"{'Заказы:':<20} среднее {df_pred['orders_with_buffer'].mean():.2f}/час, всего {df_pred['orders_with_buffer'].sum()}")
    print(f"{'Гости:':<20}  среднее {df_pred['guests_with_buffer'].mean():.2f}/час, всего {df_pred['guests_with_buffer'].sum()}")
    
    working_mask = (df_pred['hour'] >= WORKING_HOUR_START) & (df_pred['hour'] < WORKING_HOUR_END)
    night_mask = ~working_mask
    
    print(f"\nРабочие часы ({WORKING_HOUR_START}:00-{WORKING_HOUR_END}:00):")
    # ← Используем buffer
    print(f"   Заказы: {df_pred[working_mask]['orders_with_buffer'].mean():.2f}/час, всего {df_pred[working_mask]['orders_with_buffer'].sum()}")
    print(f"   Гости:  {df_pred[working_mask]['guests_with_buffer'].mean():.2f}/час, всего {df_pred[working_mask]['guests_with_buffer'].sum()}")
    
    print(f"\nНочные часы (00:00-{WORKING_HOUR_START}:00, {WORKING_HOUR_END}:00-23:00):")
    print(f"   Заказы: {df_pred[night_mask]['orders_with_buffer'].mean():.2f}/час, всего {df_pred[night_mask]['orders_with_buffer'].sum()}")
    print(f"   Гости:  {df_pred[night_mask]['guests_with_buffer'].mean():.2f}/час, всего {df_pred[night_mask]['guests_with_buffer'].sum()}")
    
    print(f"\nПрогноз по дням:")
    df_pred['date'] = df_pred['datetime'].dt.date
    # ← Используем buffer
    daily = df_pred.groupby('date')[['orders_with_buffer', 'guests_with_buffer']].sum()
    daily.columns = ['orders_with_buffer', 'guests_with_buffer']
    for date, row in daily.head(7).iterrows():
        print(f"   {date}: {int(row['orders_with_buffer'])} заказов (с буфером), {int(row['guests_with_buffer'])} гостей (с буфером)")