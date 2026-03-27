import pandas as pd
from typing import Optional
import numpy as np

def clean_raw_dataframe(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Очищает сырой DataFrame (поддерживает Excel и CSV).
    """
    df_clean = df.copy()
    
    stats = {
        'initial_rows': len(df_clean),
        'initial_cols': len(df_clean.columns),
        'duplicates_removed': 0,
        'nulls_filled': 0,
        'invalid_rows_removed': 0
    }
    
    # Нормализация имён колонок (русские → английские)
    df_clean = _normalize_column_names(df_clean)
    
    # Создание order_id если нет
    if 'order_id' not in df_clean.columns:
        if 'check_number' in df_clean.columns:
            df_clean['order_id'] = df_clean['check_number']
        else:
            df_clean['order_id'] = range(len(df_clean))
    
    # Создание order_datetime если нет
    if 'order_datetime' not in df_clean.columns:
        for col in ['open_time', 'account_date', 'Учетный день']:
            if col in df_clean.columns:
                df_clean['order_datetime'] = pd.to_datetime(df_clean[col], errors='coerce')
                break
        if 'order_datetime' not in df_clean.columns:
            df_clean['order_datetime'] = pd.NaT
    
    # 1. Удаление дубликатов
    initial_count = len(df_clean)
    if 'order_id' in df_clean.columns:
        df_clean = df_clean.drop_duplicates(subset=['order_id'], keep='first')
    stats['duplicates_removed'] = initial_count - len(df_clean)
    
    # 2. Стандартизация названий колонок
    df_clean.columns = (
        df_clean.columns
        .str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('-', '_')
    )
    
    # 3. Преобразование типов данных
    if 'order_datetime' in df_clean.columns:
        df_clean['order_datetime'] = pd.to_datetime(df_clean['order_datetime'], errors='coerce')
    
    numeric_cols = ['year', 'month', 'day', 'hour', 'minute', 'items_count', 'table_number', 'service_time_min']
    for col in numeric_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    money_cols = ['total_bill', 'tips']
    for col in money_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    # 4. Обработка пропусков
    critical_cols = ['order_id', 'order_datetime']
    for col in critical_cols:
        if col in df_clean.columns:
            null_count = df_clean[col].isnull().sum()
            if null_count > 0:
                df_clean = df_clean.dropna(subset=[col])
                stats['invalid_rows_removed'] += null_count
    
    # 5. Валидация значений
    if 'total_bill' in df_clean.columns:
        invalid = df_clean['total_bill'] < 0
        if invalid.sum() > 0:
            df_clean = df_clean[~invalid]
            stats['invalid_rows_removed'] += invalid.sum()
    
    # 6. Сортировка по времени
    if 'order_datetime' in df_clean.columns:
        df_clean = df_clean.sort_values('order_datetime').reset_index(drop=True)
    
    if verbose:
        print("=" * 50)
        print("ОТЧЕТ ОЧИСТКИ ДАННЫХ")
        print("=" * 50)
        print(f"Строк до:    {stats['initial_rows']:,}")
        print(f"Строк после: {len(df_clean):,}")
        print(f"Удалено дубликатов: {stats['duplicates_removed']:,}")
        print(f"Удалено невалидных строк: {stats['invalid_rows_removed']:,}")
        print(f"Колонок: {len(df_clean.columns)}")
        print(f"\nКолонки после очистки:")
        for col in df_clean.columns:
            print(f"   - {col}")
        print("=" * 50)
    
    df_clean = df_clean.reset_index(drop=True)
    
    return df_clean


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Приводит русские названия колонок к английским.
    """
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
    
    return df