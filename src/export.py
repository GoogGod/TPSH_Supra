import pandas as pd
from pathlib import Path
from typing import Optional
import os


def save_forecast_to_csv(
    forecast_df: pd.DataFrame,
    output_path: str = None,
    include_details: bool = True,
    verbose: bool = True
) -> str:
    if output_path is None:
        from src.config import DATA_PRED_DIR
        output_path = DATA_PRED_DIR / 'forecast.csv'
    
    df_export = forecast_df.copy()
    
    # Форматирование
    df_export['forecast_datetime'] = df_export['datetime'].dt.strftime('%Y-%m-%d %H:00')
    df_export['date'] = df_export['datetime'].dt.strftime('%Y-%m-%d')
    df_export['hour'] = df_export['datetime'].dt.hour
    
    # Выбор колонок
    base_columns = [
        'forecast_datetime',
        'date',
        'hour',
        'day_of_week',
        'is_peak_hour',
        'is_weekend',
        'is_holiday',
        'orders_predicted',
        'orders_with_buffer'
    ]
    
    detail_columns = [
        'lag_orders_1h',
        'lag_orders_24h',
        'rolling_mean_24h'
    ]
    
    if include_details:
        columns_to_export = base_columns + [col for col in detail_columns if col in df_export.columns]
    else:
        columns_to_export = base_columns
    
    columns_to_export = [col for col in columns_to_export if col in df_export.columns]
    
    df_final = df_export[columns_to_export]
    
    # Сохранение
    output_path = Path(output_path)
    output_dir = output_path.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True)
    
    df_final.to_csv(
        output_path,
        index=False,
        encoding='utf-8-sig',
        date_format='%Y-%m-%d %H:%M:%S'
    )
    
    if verbose:
        print("ПРОГНОЗ СОХРАНЁН В CSV")
        print(f"Путь: {output_path.absolute()}")
        print(f"Записей (часов): {len(df_final)}")
        print(f"Колонки: {len(df_final.columns)}")
    
    return str(output_path.absolute())