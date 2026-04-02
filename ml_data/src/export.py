import pandas as pd
from pathlib import Path
from typing import Optional, Union
import os


def save_forecast_to_csv(
    forecast_df: pd.DataFrame,
    output_path: Union[str, Path],
    include_details: bool = False,
    verbose: bool = True
) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # ← Сохраняем с буфером как основные колонки
    columns_to_save = [
        'datetime',
        'hour',
        'day_of_week',
        'is_peak_hour',
        'is_weekend',
        'is_holiday',
        'orders_predicted',
        'orders_with_buffer',  # ← Буфер
        'guests_predicted',
        'guests_with_buffer',  # ← Буфер
    ]
    
    if include_details:
        columns_to_save.extend([
            'lag_orders_1h',
            'lag_orders_24h',
            'rolling_mean_24h'
        ])
    
    # Проверяем наличие колонок
    available_columns = [col for col in columns_to_save if col in forecast_df.columns]
    
    forecast_df[available_columns].to_csv(output_path, index=False, encoding='utf-8-sig')
    
    if verbose:
        print(f"ПРОГНОЗ СОХРАНЁН В CSV")
        print(f"Путь: {output_path.absolute()}")
        print(f"Записей (часов): {len(forecast_df)}")
        print(f"Колонки: {len(available_columns)}")
        # ← Вывод с буфером
        print(f"Всего заказов (с буфером): {forecast_df['orders_with_buffer'].sum():,}")
        print(f"Всего гостей (с буфером): {forecast_df['guests_with_buffer'].sum():,}")
    
    return str(output_path)