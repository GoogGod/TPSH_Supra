import pandas as pd
from pathlib import Path
from src.config import DATA_RAW_DIR, DATA_PROC_DIR
from src.data.weather_parser import WeatherParser, merge_weather_with_orders


def prepare_real_dataset(
    input_file: str = None,
    output_file: str = None,
    add_weather: bool = True,
    verbose: bool = True
):
    """
    Подготавливает реальный датасет: добавляет погоду, сохраняет в CSV.
    """
    if input_file is None:
        input_file = f'{DATA_RAW_DIR}/real_orders.xlsx'
    
    if output_file is None:
        output_file = f'{DATA_PROC_DIR}/real_orders_with_weather.csv'
    
    if verbose:
        print(f"Загрузка данных из: {input_file}")
    
    df = pd.read_excel(input_file)
    
    if verbose:
        print(f"Загружено {len(df)} записей")
        print(f"Колонки: {list(df.columns)}")
    
    if add_weather:
        if verbose:
            print("\nДобавление погодных данных...")
        
        if 'Время открытия' in df.columns:
            df['order_datetime'] = pd.to_datetime(df['Время открытия'])
        elif 'Учетный день' in df.columns:
            df['order_datetime'] = pd.to_datetime(df['Учетный день'])
        
        date_min = df['order_datetime'].min().strftime('%Y-%m-%d')
        date_max = df['order_datetime'].max().strftime('%Y-%m-%d')
        
        weather_parser = WeatherParser(
            latitude=43.1056,
            longitude=131.8735
        )
        
        weather_df = weather_parser.get_weather_for_date_range(
            date_min,
            date_max,
            verbose=verbose
        )
        
        df = merge_weather_with_orders(df, weather_df, verbose=verbose)
    
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    if verbose:
        print(f"\nДатасет сохранён: {output_file}")
        print(f"Всего записей: {len(df)}")
        print(f"Колонки: {list(df.columns)}")
    
    return df


if __name__ == '__main__':
    prepare_real_dataset(verbose=True)