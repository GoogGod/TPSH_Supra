from src.data.process_raw_data import process_raw_data
from src.data.loader import load_raw_dataset
from src.data.preprocessor import prepare_features
from src.models.train import train
from src.models.predict import predict
from src.models.evaluate import evaluate_model
from src.export import save_forecast_to_csv
from src.config import (
    RAW_EXCEL_FILE, RAW_DATA_FILE,
    MODEL_FILE, DATA_PRED_DIR, FEATURE_COLS
)
from pathlib import Path
from typing import Optional, Union
from datetime import datetime
import os


def main(
    process_data: bool = True,
    train_model: bool = True,
    make_forecast: bool = True,
    evaluate: bool = True,
    from_date: Optional[Union[str, datetime]] = None,
    to_date: Optional[Union[str, datetime]] = None,
    hours_ahead: int = 168,
    verbose: bool = True
):
    print("СИСТЕМА ПРОГНОЗИРОВАНИЯ ЗАКАЗОВ И ГОСТЕЙ")
    
    # Обработка сырых данных
    if process_data:
        print("ОБРАБОТКА СЫРЫХ ДАННЫХ")
        
        excel_exists = Path(RAW_EXCEL_FILE).exists()
        csv_exists = Path(RAW_DATA_FILE).exists()
        
        if not excel_exists:
            print(f"Исходный файл не найден: {RAW_EXCEL_FILE}")
            if not csv_exists:
                raise FileNotFoundError("Нет ни исходного Excel, ни обработанного CSV!")
            print("Используем существующий обработанный CSV")
            process_data = False
        elif csv_exists:
            excel_mtime = os.path.getmtime(RAW_EXCEL_FILE)
            csv_mtime = os.path.getmtime(RAW_DATA_FILE)
            
            if excel_mtime > csv_mtime:
                print("Excel новее CSV — переобработка данных...")
            else:
                print("CSV актуален — пропускаем обработку")
                process_data = False
        
        if process_data:
            output_path, stats = process_raw_data(
                input_file=RAW_EXCEL_FILE,
                output_file=RAW_DATA_FILE,
                verbose=verbose
            )
    
    # Загрузка и подготовка данных
    print("ЗАГРУЗКА И ПОДГОТОВКА ДАННЫХ")
    
    data = load_raw_dataset(RAW_DATA_FILE)
    
    print("\nПодготовка признаков...")
    df_agg, feature_cols = prepare_features(data, verbose=verbose)
    
    # Обучение модели
    if train_model:
        print("ОБУЧЕНИЕ МОДЕЛИ")
        
        model, metrics = train(
            df_agg=df_agg,
            feature_cols=feature_cols,
            model_type='random_forest',
            test_size=0.2,
            model_path=str(MODEL_FILE),
            verbose=verbose
        )
    else:
        print("\nПропускаем обучение модели")
        metrics = {}
    
    # Оценка модели
    if evaluate and train_model:
        print("ОЦЕНКА МОДЕЛИ")
        
        eval_metrics = evaluate_model(
            model_path=str(MODEL_FILE),
            data_path=str(RAW_DATA_FILE),
            feature_cols=feature_cols,
            target_column='orders_count',
            test_size=0.2,
            verbose=verbose
        )
    elif evaluate and not train_model:
        print("\nПропускаем оценку (модель не обучалась)")
        eval_metrics = {}
    else:
        eval_metrics = {}
    
    # Прогноз
    if make_forecast:
        print("ПРОГНОЗ")
        
        if from_date:
            print(f"Дата начала: {from_date}")
        if to_date:
            print(f"Дата конца: {to_date}")
        if not from_date and not to_date:
            print(f"Период: {hours_ahead} часов ({hours_ahead/24:.1f} дней)")
        
        forecast = predict(
            model_path=str(MODEL_FILE),
            raw_data_path=str(RAW_DATA_FILE),
            from_datetime=from_date,
            to_datetime=to_date,
            hours_ahead=hours_ahead,
            verbose=verbose
        )
        
        # Сохранение прогноза
        print("СОХРАНЕНИЕ ПРОГНОЗА")
        
        csv_path = save_forecast_to_csv(
            forecast,
            output_path=f'{DATA_PRED_DIR}/forecast.csv',
            include_details=False,
            verbose=verbose
        )
    else:
        print("\nПропускаем прогноз")
        csv_path = None
        forecast = None
    
    # ИТОГИ
    print("ПАЙПЛАЙН ЗАВЕРШЁН")
    
    if csv_path:
        print(f"\nПрогноз сохранён: {csv_path}")
    
    if forecast is not None:
        print(f"\nПериод прогноза:")
        print(f"   С: {forecast['datetime'].min()}")
        print(f"   По: {forecast['datetime'].max()}")
        print(f"   Всего часов: {len(forecast)}")
        print(f"   Всего заказов: {forecast['orders_predicted'].sum()}")
        print(f"   Всего гостей: {forecast['guests_predicted'].sum()}")
        print(f"   Среднее в час: {forecast['orders_predicted'].mean():.2f} заказов, {forecast['guests_predicted'].mean():.2f} гостей")
    

if __name__ == '__main__':
    main(
        process_data=True,
        train_model=True,
        make_forecast=True,
        evaluate=True,
        verbose=True,
        from_date='2026-01-01',
        to_date='2027-01-01'
    )