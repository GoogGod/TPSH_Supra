from src.data.process_raw_data import process_raw_data
from src.data.loader import load_raw_dataset, load_and_merge_new_data
from src.data.preprocessor import prepare_features
from src.models.train import train
from src.models.predict import predict
from src.models.evaluate import evaluate_model
from src.export import save_forecast_to_csv
from src.config import (
    RAW_EXCEL_FILE, RAW_DATA_FILE,
    MODEL_FILE, DATA_PRED_DIR, FEATURE_COLS, DATA_RAW_NEW_DIR
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
    make_schedule: bool = True,
    incremental_training: bool = False,
    model_type: str = 'xgboost',
    num_waiters: int = 6,
    waiter_config: dict = None,
    from_date: Optional[Union[str, datetime]] = None,
    to_date: Optional[Union[str, datetime]] = None,
    hours_ahead: int = 168,
    verbose: bool = True,
    force_fresh_weather: bool = True
):
    print("СИСТЕМА ПРОГНОЗИРОВАНИЯ ЗАКАЗОВ И ГОСТЕЙ")
    
    # Обработка сырых данных
    if process_data:        
        output_path, stats = process_raw_data(
            input_file=RAW_EXCEL_FILE,
            output_file=RAW_DATA_FILE,
            verbose=verbose,
            force_reprocess=True
        )

    # Загрузка и подготовка данных
    print("\nЗАГРУЗКА И ПОДГОТОВКА ДАННЫХ")
    
    # Проверка новых данных
    new_dir = Path(DATA_RAW_NEW_DIR) if not isinstance(DATA_RAW_NEW_DIR, Path) else DATA_RAW_NEW_DIR
    has_new_data = new_dir.exists() and list(new_dir.glob('*.xlsx'))
    
    if has_new_data:
        print("\nОБНАРУЖЕНЫ НОВЫЕ ДАННЫЕ")
        print(f"Папка: {new_dir}")
        
        data = load_and_merge_new_data(
            processed_path=RAW_DATA_FILE,
            new_data_folder=new_dir,
            verbose=verbose
        )
        
        # Переобрабатываем погоду для объединённых данных
        if process_data:
            print("\nОбновление погодных данных...")
            process_raw_data(
                input_file=RAW_EXCEL_FILE,
                output_file=RAW_DATA_FILE,
                verbose=verbose,
                force_reprocess=True
            )
            data = load_raw_dataset(RAW_DATA_FILE)
    else:
        data = load_raw_dataset(RAW_DATA_FILE)
    
    print("\nПодготовка признаков...")
    df_agg, feature_cols = prepare_features(data, verbose=verbose)
    
    # Обучение модели
    if train_model:
        print("\nОБУЧЕНИЕ МОДЕЛИ")
        
        existing_model_path = None
        if incremental_training and os.path.exists(MODEL_FILE):
            existing_model_path = str(MODEL_FILE)
            if verbose:
                print(f"Найдена существующая модель: {existing_model_path}")
                print(f"Режим: дообучение")
        else:
            if verbose:
                print(f"Режим: полное обучение")
        
        model, metrics = train(
            df_agg=df_agg,
            feature_cols=feature_cols,
            model_type=model_type,
            test_size=0.2,
            model_path=str(MODEL_FILE),
            verbose=verbose,
            existing_model_path=existing_model_path,
            incremental=incremental_training
        )
    else:
        print("\nПропускаем обучение модели")
        metrics = {}
    
    # Оценка модели
    if evaluate and train_model:        
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
    forecast = None
    csv_path = None
    
    if make_forecast:
        print("\nПРОГНОЗ")
        
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
            verbose=verbose,
            force_fresh_weather=force_fresh_weather
        )
        
        print("\nСОХРАНЕНИЕ ПРОГНОЗА")
        
        csv_path = save_forecast_to_csv(
            forecast,
            output_path=f'{DATA_PRED_DIR}/forecast.csv',
            include_details=False,
            verbose=verbose
        )
    else:
        print("\nПропускаем прогноз")
    
    # Планирование смен
    if make_schedule and forecast is not None:
        print("\nПЛАНИРОВАНИЕ СМЕН ОФИЦИАНТОВ")
        
        from scheduler import create_waiter_schedule
        
        if waiter_config is None:
            waiter_config = {
                1: 'specialist', 2: 'specialist', 3: 'specialist',
                4: 'novice', 5: 'novice', 6: 'novice'
            }
        
        schedule_df, schedule_stats = create_waiter_schedule(
            forecast_path=f'{DATA_PRED_DIR}/forecast.csv',
            waiter_config=waiter_config,
            output_path=f'{DATA_PRED_DIR}/waiter_schedule.csv',
            verbose=verbose
        )
    else:
        print("\nПропускаем планирование смен")
        schedule_df = None
        schedule_stats = {}
    
    # ИТОГИ
    print("ПАЙПЛАЙН ЗАВЕРШЁН")
    
    if csv_path:
        print(f"\nПрогноз сохранён: {csv_path}")
    
    if forecast is not None:
        print(f"\nПериод прогноза:")
        print(f"   С: {forecast['datetime'].min()}")
        print(f"   По: {forecast['datetime'].max()}")
        print(f"   Всего часов: {len(forecast)}")
        print(f"   Всего заказов: {forecast['orders_with_buffer'].sum()} (с буфером +25%)")
        print(f"   Всего гостей: {forecast['guests_with_buffer'].sum()} (с буфером +25%)")
        print(f"   Среднее в час: {forecast['orders_with_buffer'].mean():.2f} заказов, {forecast['guests_with_buffer'].mean():.2f} гостей")
    
    if schedule_df is not None:
        print(f"\nРасписание официантов:")
        print(f"   Файл: {DATA_PRED_DIR}/waiter_schedule.csv")
        print(f"   Количество официантов: {num_waiters}")
        print(f"   Всего смен: {schedule_stats.get('total_shifts', 0)}")
    
    if metrics:
        print(f"\nМетрики модели:")
        print(f"   Тип: {metrics.get('model_type', 'N/A')}")
        print(f"   R² (Test): {metrics.get('test_r2', 0):.3f}")
        print(f"   MAE (Test): {metrics.get('test_mae', 0):.2f}")
        if 'training_date' in metrics:
            print(f"   Дата обучения: {metrics['training_date']}")


if __name__ == '__main__':
    waiter_config = {
        1: 'specialist', 2: 'specialist', 3: 'specialist', 4: 'specialist', 5: 'specialist', 6: 'specialist', 7: 'specialist',
        8: 'novice', 9: 'novice'
    }
    
    main(
        process_data=True,
        train_model=True,
        make_forecast=True,
        evaluate=True,
        make_schedule=True,
        incremental_training=False,
        model_type='xgboost',
        num_waiters=9,
        waiter_config=waiter_config,
        verbose=True,
        force_fresh_weather=True,
        from_date='2026-03-01',
        to_date='2026-05-01'
    )