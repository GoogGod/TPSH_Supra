import pandas as pd
import numpy as np
import joblib
from typing import Optional, Union
from datetime import datetime, timedelta
import os
from src.config import (
    MODEL_FILE, RAW_DATA_FILE, 
    WORKING_HOUR_START, WORKING_HOUR_END, 
    MIN_ORDERS_PER_HOUR
)
from src.data.loader import load_raw_dataset
from src.data.preprocessor import prepare_for_prediction, prepare_features


def predict(
    model_path: str = None,
    raw_data_path: str = None,
    from_datetime: Optional[Union[str, datetime]] = None,
    to_datetime: Optional[Union[str, datetime]] = None,
    hours_ahead: int = 168,
    verbose: bool = True
) -> pd.DataFrame:
    model_path = model_path or str(MODEL_FILE)
    raw_data_path = raw_data_path or str(RAW_DATA_FILE)
    
    if verbose:
        print("ПРОГНОЗ КОЛИЧЕСТВА ЗАКАЗОВ ПО ЧАСАМ")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Модель не найдена: {model_path}")
    
    model_data = joblib.load(model_path)
    model = model_data['model']
    feature_cols = model_data['feature_cols']
    
    # Загружаем коэффициент гостей
    avg_guests_per_order = model_data.get('avg_guests_per_order', 2.3)
    
    if verbose:
        print(f"Модель: {model_data['metrics']['model_type']}")
        print(f"Признаков: {len(feature_cols)}")
        print(f"Среднее гостей на заказ: {avg_guests_per_order:.2f}")
    
    # Загрузка и подготовка истории
    df = load_raw_dataset(raw_data_path)
    df = _clean_for_predict(df)
    
    hist_agg, _ = prepare_features(df, verbose=False)
    last_hist_datetime = hist_agg['datetime'].max()
    
    if verbose:
        print(f"История: {hist_agg['datetime'].min()} — {last_hist_datetime}")
    
    # Определение диапазона прогноза
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
    
    # Подготовка данных для предсказания
    df_pred, _ = prepare_for_prediction(
        hist_agg,
        from_datetime,
        to_datetime,
        feature_cols,
        verbose=verbose
    )
    
    # Предсказание заказов
    X_pred = df_pred[feature_cols]
    predictions = model.predict(X_pred)
    
    df_pred['orders_predicted'] = np.maximum(0, np.round(predictions)).astype(int)
    
    # Прогноз гостей через конверсию
    df_pred['guests_predicted'] = (df_pred['orders_predicted'] * avg_guests_per_order).round().astype(int)
    
    # Буферы (+25%)
    df_pred['orders_with_buffer'] = (df_pred['orders_predicted'] * 1.25).astype(int)
    df_pred['guests_with_buffer'] = (df_pred['guests_predicted'] * 1.25).astype(int)
    
    # Минимальный порог в рабочие часы
    working_hours_mask = (
        (df_pred['hour'] >= WORKING_HOUR_START) & 
        (df_pred['hour'] < WORKING_HOUR_END)
    )
    
    df_pred.loc[working_hours_mask, 'orders_predicted'] = df_pred.loc[
        working_hours_mask, 'orders_predicted'
    ].clip(lower=MIN_ORDERS_PER_HOUR)
    
    df_pred.loc[working_hours_mask, 'guests_predicted'] = df_pred.loc[
        working_hours_mask, 'guests_predicted'
    ].clip(lower=1)
    
    df_pred.loc[working_hours_mask, 'orders_with_buffer'] = df_pred.loc[
        working_hours_mask, 'orders_with_buffer'
    ].clip(lower=MIN_ORDERS_PER_HOUR)
    
    df_pred.loc[working_hours_mask, 'guests_with_buffer'] = df_pred.loc[
        working_hours_mask, 'guests_with_buffer'
    ].clip(lower=1)
    
    if verbose:
        _print_forecast_report(df_pred)
    
    return df_pred[['datetime', 'hour', 'day_of_week', 'is_peak_hour', 
                    'is_weekend', 'is_holiday', 
                    'orders_predicted', 'orders_with_buffer',
                    'guests_predicted', 'guests_with_buffer',
                    'lag_orders_1h', 'lag_orders_24h', 'rolling_mean_24h']]


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
    print("\nПРОГНОЗ ПО ЧАСАМ (первые 24 часа)")
    print(f"{'Дата-время':<20} {'Час':<5} {'День':<5} {'Пик':<4} {'Заказов':<9} {'Гостей':<10}")
    print("-" * 65)
    
    day_names = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}
    
    for _, row in df_pred.head(24).iterrows():
        dt_str = row['datetime'].strftime('%Y-%m-%d %H:00')
        day_name = day_names.get(row['day_of_week'], '')
        peak = '1' if row['is_peak_hour'] else '0'
        print(f"{dt_str:<20} {row['hour']:<5} {day_name:<5} {peak:<4} {row['orders_predicted']:<9} {row['guests_predicted']:<10}")
    
    print(f"\nВсего часов прогноза: {len(df_pred)}")
    print(f"{'Заказы:':<20} среднее {df_pred['orders_predicted'].mean():.2f}/час, всего {df_pred['orders_predicted'].sum()}")
    print(f"{'Гости:':<20}  среднее {df_pred['guests_predicted'].mean():.2f}/час, всего {df_pred['guests_predicted'].sum()}")
    
    peak_avg_orders = df_pred[df_pred['is_peak_hour'] == 1]['orders_predicted'].mean()
    offpeak_avg_orders = df_pred[df_pred['is_peak_hour'] == 0]['orders_predicted'].mean()
    peak_avg_guests = df_pred[df_pred['is_peak_hour'] == 1]['guests_predicted'].mean()
    offpeak_avg_guests = df_pred[df_pred['is_peak_hour'] == 0]['guests_predicted'].mean()
    
    print(f"\nСреднее в пиковые часы: {peak_avg_orders:.2f} заказов, {peak_avg_guests:.2f} гостей")
    print(f"Среднее в непиковые: {offpeak_avg_orders:.2f} заказов, {offpeak_avg_guests:.2f} гостей")
    
    # Прогноз по дням
    print(f"\nПрогноз по дням:")
    df_pred['date'] = df_pred['datetime'].dt.date
    daily = df_pred.groupby('date')[['orders_predicted', 'guests_predicted']].sum()
    for date, row in daily.head(7).iterrows():
        print(f"   {date}: {int(row['orders_predicted'])} заказов, {int(row['guests_predicted'])} гостей")