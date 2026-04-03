import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple
from datetime import datetime
from src.config import DATA_RAW_DIR, DATA_PROC_DIR, WEATHER_LATITUDE, WEATHER_LONGITUDE
from src.data.weather_parser import WeatherParser, merge_weather_with_orders


def analyze_raw_data(file_path: str) -> dict:
    # Читаем без заголовков
    df = pd.read_excel(file_path, header=None)
    
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
    
    if len(df) < 1:
        stats['missing_columns'] = ['Нет данных в файле']
        return stats
    
    # Проверяем первую строку на наличие итогов
    first_row = df.iloc[0]
    has_totals = False
    
    for val in first_row:
        val_str = str(val).replace(',', '').replace('.', '').strip()
        if val_str.isdigit() and len(val_str) > 3:
            has_totals = True
            break
    
    if has_totals:
        df = df.iloc[1:].reset_index(drop=True)
        stats['total_rows'] = len(df)
    
    if len(df) < 1:
        stats['missing_columns'] = ['Нет данных после пропуска итогов']
        return stats
    
    # Проверяем вторую строку на заголовки
    second_row = df.iloc[0]
    has_headers = False
    
    for val in second_row:
        val_str = str(val)
        if any(k in val_str for k in ['Отделение', 'Учет', 'Номер', 'Время', 'Заказ', 'Гость']):
            has_headers = True
            break
    
    if has_headers:
        df.columns = df.iloc[0]
        df = df[1:]
    
    # Маппинг русских названий
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
    
    # Если не получилось - позиционный маппинг
    required_cols = ['open_time', 'check_number', 'orders_count', 'guests_count']
    missing = [col for col in required_cols if col not in df.columns]
    
    if missing and len(df.columns) >= 7:
        df.columns = ['department', 'account_date', 'check_number', 
                      'open_time', 'close_time', 'orders_count', 'guests_count']
    
    for col in required_cols:
        if col not in df.columns:
            stats['missing_columns'].append(col)
    
    if 'open_time' in df.columns:
        df['order_datetime'] = pd.to_datetime(df['open_time'], errors='coerce')
        valid_dates = df['order_datetime'].notna().sum()
        stats['date_range'] = {
            'min': df['order_datetime'].min(),
            'max': df['order_datetime'].max(),
            'valid_count': valid_dates,
            'total_count': len(df)
        }
        stats['unique_days'] = df['order_datetime'].dt.date.nunique()
    
    if 'orders_count' in df.columns:
        df['orders_count'] = pd.to_numeric(df['orders_count'], errors='coerce')
        stats['orders_total'] = df['orders_count'].sum()
        stats['orders_per_day'] = stats['orders_total'] / max(stats['unique_days'], 1)
    
    if 'guests_count' in df.columns:
        df['guests_count'] = pd.to_numeric(df['guests_count'], errors='coerce')
        stats['guests_total'] = df['guests_count'].sum()
        if stats['orders_total'] > 0:
            stats['guests_per_order'] = stats['guests_total'] / stats['orders_total']
    
    return stats

def create_enhanced_dataset(
    input_file: str,
    output_file: str,
    weather_df: pd.DataFrame = None,
    verbose: bool = True
) -> pd.DataFrame:
    if verbose:
        print("Загрузка данных...")
    
    # Читаем без заголовков
    df = pd.read_excel(input_file, header=None)
    
    if len(df) < 2:
        raise ValueError("Файл пуст или содержит менее 2 строк")
    
    # Проверяем первую строку на наличие итогов (цифры в любых колонках)
    first_row = df.iloc[0]
    has_totals = False
    
    for val in first_row:
        val_str = str(val).replace(',', '').replace('.', '').strip()
        if val_str.isdigit() and len(val_str) > 3:
            has_totals = True
            break
    
    if has_totals:
        # Первая строка - итоги, данные начинаются со строки 1
        if verbose:
            print("  Обнаружена строка итогов - пропускаем")
        df = df.iloc[1:].reset_index(drop=True)
    
    if len(df) < 1:
        raise ValueError("Нет данных после пропуска строки итогов")
    
    # Проверяем вторую строку - если это заголовки (русский текст), используем их
    second_row = df.iloc[0]
    has_headers = False
    
    for val in second_row:
        val_str = str(val)
        # Проверяем на русские заголовки
        if any(k in val_str for k in ['Отделение', 'Учет', 'Номер', 'Время', 'Заказ', 'Гость']):
            has_headers = True
            break
    
    if has_headers:
        # Вторая строка - заголовки, используем их
        if verbose:
            print("  Обнаружены заголовки - используем как названия колонок")
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)
    
    if len(df) < 1:
        raise ValueError("Нет данных после пропуска заголовков")
    
    # Маппинг русских названий на английские
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
    
    # Если колонки всё ещё не те - пробуем позиционный маппинг
    required = ['open_time', 'orders_count', 'guests_count']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        if verbose:
            print("  Заголовки не распознаны - используем позиционный маппинг")
        
        if len(df.columns) >= 7:
            df.columns = ['department', 'account_date', 'check_number', 
                          'open_time', 'close_time', 'orders_count', 'guests_count'][:len(df.columns)]
    
    # Финальная проверка
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Отсутствуют колонки: {missing}. Доступные: {list(df.columns)}")
    
    # Парсинг даты/времени
    def parse_datetime(val):
        if pd.isna(val):
            return pd.NaT
        for fmt in ['%m/%d/%Y %H:%M', '%d.%m.%Y %H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M']:
            try:
                return datetime.strptime(str(val).strip(), fmt)
            except:
                continue
        return pd.to_datetime(val, errors='coerce')
    
    df['order_datetime'] = df['open_time'].apply(parse_datetime)
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
        checks_count=('check_number', 'count') if 'check_number' in df.columns else ('orders_count', 'count'),
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