import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple
from src.config import DATA_RAW_DIR, DATA_PROC_DIR, WEATHER_LATITUDE, WEATHER_LONGITUDE
from src.data.weather_parser import WeatherParser, merge_weather_with_orders


def analyze_raw_data(file_path: str) -> dict:
    df = pd.read_excel(file_path, header=1)
    
    stats = {
        'total_rows': len(df),
        'columns': list(df.columns),
        'date_range': None,
        'orders_total': 0,
        'guests_total': 0,
        'guests_per_order': 0,
        'unique_days': 0,
        'orders_per_day': 0,
        'missing_columns': []
    }
    
    required_cols = ['Время открытия', 'Номер чека', 'Заказов', 'Количество гостей']
    for col in required_cols:
        if col not in df.columns:
            stats['missing_columns'].append(col)
    
    if 'Время открытия' in df.columns:
        df['order_datetime'] = pd.to_datetime(df['Время открытия'], errors='coerce')
        valid_dates = df['order_datetime'].notna().sum()
        stats['date_range'] = {
            'min': df['order_datetime'].min(),
            'max': df['order_datetime'].max(),
            'valid_count': valid_dates,
            'total_count': len(df)
        }
        stats['unique_days'] = df['order_datetime'].dt.date.nunique()
    
    if 'Заказов' in df.columns:
        stats['orders_total'] = df['Заказов'].sum()
        stats['orders_per_day'] = stats['orders_total'] / max(stats['unique_days'], 1)
    
    if 'Количество гостей' in df.columns:
        stats['guests_total'] = df['Количество гостей'].sum()
        if stats['orders_total'] > 0:
            stats['guests_per_order'] = stats['guests_total'] / stats['orders_total']
    
    if 'Время открытия' in df.columns:
        df['hour'] = df['order_datetime'].dt.hour
        stats['hours_distribution'] = df.groupby('hour')['Заказов'].sum().to_dict()
    
    if 'Время открытия' in df.columns:
        df['day_name'] = df['order_datetime'].dt.day_name()
        stats['dow_distribution'] = df.groupby('day_name')['Заказов'].sum().to_dict()
    
    return stats


def create_enhanced_dataset(
    input_file: str,
    output_file: str,
    weather_df: pd.DataFrame = None,
    verbose: bool = True
) -> pd.DataFrame:
    if verbose:
        print("Загрузка данных...")
    
    df = pd.read_excel(input_file, header=1)
    
    mapping = {
        'Отделение': 'department',
        'Учетный день': 'account_date',
        'Номер чека': 'check_number',
        'Время открытия': 'open_time',
        'Время закрытия': 'close_time',
        'Заказов': 'orders_count',
        'Количество гостей': 'guests_count'
    }
    df = df.rename(columns=mapping)
    
    df['order_datetime'] = pd.to_datetime(df['open_time'], errors='coerce')
    df = df.dropna(subset=['order_datetime'])
    
    df['hour'] = df['order_datetime'].dt.hour
    df['day_of_week'] = df['order_datetime'].dt.weekday
    df['date'] = df['order_datetime'].dt.date
    df['month'] = df['order_datetime'].dt.month
    df['year'] = df['order_datetime'].dt.year
    
    df = df[(df['hour'] >= 10) & (df['hour'] < 23)]
    
    df_agg = df.groupby(df['order_datetime'].dt.floor('h')).agg(
        orders_count=('orders_count', 'sum'),
        guests_count=('guests_count', 'sum'),
        checks_count=('check_number', 'count'),
        avg_guests_per_check=('guests_count', 'mean'),
    ).reset_index()
    
    df_agg.rename(columns={'order_datetime': 'datetime'}, inplace=True)
    
    full_range = pd.date_range(
        start=df_agg['datetime'].min(),
        end=df_agg['datetime'].max(),
        freq='h'
    )
    df_agg = df_agg.set_index('datetime').reindex(full_range, fill_value=0)
    df_agg = df_agg.reset_index().rename(columns={'index': 'datetime'})
    
    if weather_df is not None and len(weather_df) > 0:
        if verbose:
            print(f"Слияние с погодными данными: {len(weather_df)} записей")
        
        weather_df = weather_df.copy()
        weather_df['datetime'] = pd.to_datetime(weather_df['date']).dt.floor('h')
        
        df_agg = df_agg.merge(
            weather_df.drop(columns=['date'], errors='ignore'),
            on='datetime',
            how='left'
        )
        
        weather_cols = ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']
        for col in weather_cols:
            if col in df_agg.columns:
                if df_agg[col].notna().any():
                    df_agg[col] = df_agg[col].fillna(df_agg[col].median())
                else:
                    df_agg[col] = 0
    
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_agg.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    if verbose:
        print(f"Улучшенный датасет сохранён: {output_file}")
        print(f"Всего часов: {len(df_agg)}")
        print(f"Заказов всего: {df_agg['orders_count'].sum():,}")
        print(f"Среднее заказов/час: {df_agg['orders_count'].mean():.2f}")
        
        if 'temperature_mean' in df_agg.columns:
            print(f"Температура: мин={df_agg['temperature_mean'].min():.1f}°, макс={df_agg['temperature_mean'].max():.1f}°")
    
    return df_agg


def process_raw_data(
    input_file: str = None,
    output_file: str = None,
    verbose: bool = True,
    force_reprocess: bool = True
) -> Tuple[str, dict]:
    if input_file is None:
        input_file = f'{DATA_RAW_DIR}/real_orders.xlsx'
    
    if output_file is None:
        output_file = f'{DATA_PROC_DIR}/processed_orders.csv'
    
    input_file = Path(input_file)
    output_file = Path(output_file)
    
    if not input_file.exists():
        raise FileNotFoundError(f"Исходный файл не найден: {input_file}")
    
    if verbose:
        print("ОБРАБОТКА СЫРЫХ ДАННЫХ")
    
    # Анализ
    if verbose:
        print("\nАнализ сырых данных...")
    stats = analyze_raw_data(input_file)
    
    if verbose:
        print(f"Всего строк: {stats['total_rows']:,}")
        print(f"Уникальных дней: {stats['unique_days']}")
        print(f"Всего заказов: {stats['orders_total']:,}")
        print(f"В среднем в день: {stats['orders_per_day']:.1f}")
        
        if stats['missing_columns']:
            print(f"Отсутствуют колонки: {stats['missing_columns']}")
    
    # Загрузка погодных данных для дат из датасета
    if verbose:
        print("\nЗагрузка погодных данных...")
    
    date_range = stats['date_range']
    weather_df = None
    
    if date_range and date_range['min'] and date_range['max']:
        start_date = date_range['min'].strftime('%Y-%m-%d')
        end_date = date_range['max'].strftime('%Y-%m-%d')
        
        weather_parser = WeatherParser(
            latitude=WEATHER_LATITUDE,
            longitude=WEATHER_LONGITUDE
        )
        
        weather_df = weather_parser.get_weather_for_date_range(
            start_date=start_date,
            end_date=end_date,
            verbose=verbose
        )
    else:
        if verbose:
            print("Не удалось определить диапазон дат — погода не загружена")
    
    # Обработка
    if verbose:
        print("\nСоздание улучшенного датасета...")
    
    df_processed = create_enhanced_dataset(
        input_file=input_file,
        output_file=output_file,
        weather_df=weather_df,
        verbose=verbose
    )
    
    if verbose:
        print("ОБРАБОТКА ЗАВЕРШЕНА")
        print(f"Исходный файл: {input_file}")
        print(f"Обработанный файл: {output_file}")
    
    return str(output_file), stats


if __name__ == '__main__':
    process_raw_data(verbose=True)