import pandas as pd
from pathlib import Path
from typing import Union, List, Optional
from datetime import datetime


def load_raw_dataset(file_path: Union[str, Path]) -> pd.DataFrame:
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path.absolute()}")
    
    if file_path.suffix.lower() == '.csv':
        df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
    elif file_path.suffix.lower() == '.xlsx':
        df = pd.read_excel(file_path, header=1)
    else:
        raise ValueError(f"Неподдерживаемый формат: {file_path.suffix}")
    
    print(f"Загружено {len(df)} записей из {file_path.name}")
    print(f"Колонки: {list(df.columns)}")
    
    return df


def load_and_merge_new_data(
    processed_path: Union[str, Path],
    new_data_folder: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    verbose: bool = True
) -> pd.DataFrame:
    processed_path = Path(processed_path)
    new_data_folder = Path(new_data_folder)
    
    if not processed_path.exists():
        raise FileNotFoundError(f"Основной файл не найден: {processed_path}")
    
    if not new_data_folder.exists():
        if verbose:
            print(f"Папка с новыми данными не найдена: {new_data_folder}")
        return load_raw_dataset(processed_path)
    
    new_files: List[Path] = list(new_data_folder.glob('*.xlsx'))
    
    if not new_files:
        if verbose:
            print("Новых файлов не найдено")
        return load_raw_dataset(processed_path)
    
    if verbose:
        print(f"Найдено {len(new_files)} новых файлов")
    
    old_df = pd.read_csv(processed_path, encoding='utf-8-sig', parse_dates=['datetime'])
    
    if verbose:
        print(f"Старые данные: {len(old_df)} записей")
        print(f"Диапазон дат: {old_df['datetime'].min()} — {old_df['datetime'].max()}")
    
    new_dfs = []
    for file in new_files:
        if verbose:
            print(f"\nОбработка {file.name}...")
        
        try:
            raw_df = pd.read_excel(file, header=1)
            processed_new = _process_new_file(raw_df, verbose=verbose)
            new_dfs.append(processed_new)
            
            if verbose:
                print(f"{file.name}: {len(processed_new)} записей")
                
        except Exception as e:
            if verbose:
                print(f"Ошибка {file.name}: {e}")
    
    if not new_dfs:
        if verbose:
            print("Не удалось обработать ни один файл")
        return old_df
    
    combined_new = pd.concat(new_dfs, ignore_index=True)
    
    if verbose:
        print(f"\nНовые данные: {len(combined_new)} записей")
        print(f"Диапазон дат: {combined_new['datetime'].min()} — {combined_new['datetime'].max()}")
    
    merged_df = pd.concat([old_df, combined_new], ignore_index=True)
    
    before_dedup = len(merged_df)
    merged_df = merged_df.drop_duplicates(subset=['datetime'], keep='last')
    after_dedup = len(merged_df)
    
    if verbose:
        print(f"\nУдалено дубликатов: {before_dedup - after_dedup}")
    
    merged_df = merged_df.sort_values('datetime').reset_index(drop=True)
    
    save_path = output_path if output_path else processed_path
    merged_df.to_csv(save_path, index=False, encoding='utf-8-sig')
    
    if verbose:
        print(f"\nОбъединённый файл сохранён: {save_path}")
        print(f"  Всего записей: {len(merged_df)}")
        print(f"  Диапазон дат: {merged_df['datetime'].min()} — {merged_df['datetime'].max()}")
    
    return merged_df


def _process_new_file(raw_df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    df = raw_df.copy()
    
    # Проверка: если первая колонка содержит "Терраса" или похожие значения,
    # значит заголовков нет — используем позиционный маппинг
    first_col_sample = str(df.iloc[0, 0]).lower() if len(df) > 0 else ''
    
    if 'террас' in first_col_sample or 'зал' in first_col_sample or first_col_sample.isdigit():
        # Позиционный маппинг (без заголовков)
        if verbose:
            print("  Режим: позиционный маппинг (файл без заголовков)")
        
        # Проверяем, что колонок достаточно
        if len(df.columns) < 6:
            raise ValueError(f"Ожидается минимум 6 колонок, найдено: {len(df.columns)}")
        
        # Переименование по позициям
        df.columns = ['department', 'account_date', 'check_number', 
                      'open_time', 'close_time', 'orders_count', 'guests_count'][:len(df.columns)]
    else:
        # Маппинг по названиям колонок (автоматическое определение)
        column_mapping = {}
        
        for col in df.columns:
            col_str = str(col).lower()
            if any(k in col_str for k in ['время', 'open', 'time', 'открыт']):
                column_mapping[col] = 'open_time'
            elif any(k in col_str for k in ['чек', 'номер', 'check']):
                column_mapping[col] = 'check_number'
            elif any(k in col_str for k in ['заказ', 'order']):
                column_mapping[col] = 'orders_count'
            elif any(k in col_str for k in ['гость', 'guest']):
                column_mapping[col] = 'guests_count'
            elif any(k in col_str for k in ['отдел', 'depart']):
                column_mapping[col] = 'department'
            elif any(k in col_str for k in ['учет', 'account', 'date']):
                column_mapping[col] = 'account_date'
            elif any(k in col_str for k in ['закрыт', 'close']):
                column_mapping[col] = 'close_time'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
            if verbose:
                print(f"  Найдено колонок: {len(column_mapping)}")
    
    # Проверка обязательных колонок
    required = ['open_time', 'orders_count', 'guests_count']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Отсутствуют колонки: {missing}. Доступные: {list(df.columns)}")
    
    # Парсинг даты/времени (поддержка разных форматов)
    def parse_datetime(val):
        if pd.isna(val):
            return pd.NaT
        # Пробуем разные форматы
        for fmt in ['%m/%d/%Y %H:%M', '%d.%m.%Y %H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M']:
            try:
                return datetime.strptime(str(val).strip(), fmt)
            except:
                continue
        # Fallback: pandas auto-parse
        return pd.to_datetime(val, errors='coerce')
    
    df['order_datetime'] = df['open_time'].apply(parse_datetime)
    df = df.dropna(subset=['order_datetime'])
    
    # Фильтр рабочих часов
    df['hour'] = df['order_datetime'].dt.hour
    df = df[(df['hour'] >= 10) & (df['hour'] < 23)]
    
    # Агрегация по часам
    df_agg = df.groupby(df['order_datetime'].dt.floor('h')).agg(
        orders_count=('orders_count', 'sum'),
        guests_count=('guests_count', 'sum'),
        checks_count=('check_number', 'count') if 'check_number' in df.columns else ('orders_count', 'count'),
        avg_guests_per_check=('guests_count', 'mean'),
    ).reset_index()
    
    df_agg.rename(columns={'order_datetime': 'datetime'}, inplace=True)
    
    # Заполнение пропущенных часов
    full_range = pd.date_range(
        start=df_agg['datetime'].min(),
        end=df_agg['datetime'].max(),
        freq='h'
    )
    df_agg = df_agg.set_index('datetime').reindex(full_range, fill_value=0)
    df_agg = df_agg.reset_index().rename(columns={'index': 'datetime'})
    
    # Погодные колонки (заполняем нулями)
    for col in ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']:
        df_agg[col] = 0
    
    return df_agg