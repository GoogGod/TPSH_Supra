from src.data.process_raw_data import process_raw_data
from src.data.loader import load_raw_dataset
from src.data.preprocessor import prepare_features
from src.models.predict import predict
from src.models.train import train
from src.export import save_forecast_to_csv
from src.config import RAW_EXCEL_FILE, RAW_DATA_FILE, MODEL_FILE, DATA_PRED_DIR
from pathlib import Path
from typing import Optional, Union
from datetime import datetime
import os


def main(
    process_data: bool = True,
    train_model: bool = True,
    make_forecast: bool = True,
    from_date: Optional[Union[str, datetime]] = None,
    to_date: Optional[Union[str, datetime]] = None,
    hours_ahead: int = 168,
    verbose: bool = True
):
    print("=" * 70)
    print("СИСТЕМА ПРОГНОЗИРОВАНИЯ ЗАКАЗОВ")
    print("=" * 70)
    
    # ШАГ 1: Обработка сырых данных
    if process_data:
        print("\n" + "=" * 70)
        print("ШАГ 1: ОБРАБОТКА СЫРЫХ ДАННЫХ")
        print("=" * 70)
        
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
    
    # ШАГ 2: Загрузка и подготовка данных
    print("\n" + "=" * 70)
    print("ШАГ 2: ЗАГРУЗКА И ПОДГОТОВКА ДАННЫХ")
    print("=" * 70)
    
    data = load_raw_dataset(RAW_DATA_FILE)
    
    print("\nПодготовка признаков...")
    df_agg, feature_cols = prepare_features(data, verbose=verbose)
    
    # ШАГ 3: Обучение модели
    if train_model:
        print("\n" + "=" * 70)
        print("ШАГ 3: ОБУЧЕНИЕ МОДЕЛИ")
        print("=" * 70)
        
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
    
    # ШАГ 4: Прогноз
    if make_forecast:
        print("\n" + "=" * 70)
        print("ШАГ 4: ПРОГНОЗ")
        print("=" * 70)
        
        # Вывод параметров прогноза
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
        
        # ШАГ 5: Сохранение прогноза
        print("\n" + "=" * 70)
        print("ШАГ 5: СОХРАНЕНИЕ ПРОГНОЗА")
        print("=" * 70)
        
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
    print("\n" + "=" * 70)
    print("ПАЙПЛАЙН ЗАВЕРШЁН")
    print("=" * 70)
    
    if metrics:
        print(f"\nМЕТРИКИ МОДЕЛИ")
        print(f"{'=' * 40}")
        print(f"{'Метрика':<25} {'Значение':>15}")
        print(f"{'=' * 40}")
        print(f"{'MAE(test):':<25} {metrics.get('test_mae', 'N/A'):>15.2f}")
        print(f"{'RMSE(test):':<25} {metrics.get('test_rmse', 'N/A'):>15.2f}")
        print(f"{'R²(test):':<25} {metrics.get('test_r2', 'N/A'):>15.3f}")
        print(f"{'MAE(train):':<25} {metrics.get('train_mae', 'N/A'):>15.2f}")
        print(f"{'RMSE(train):':<25} {metrics.get('train_rmse', 'N/A'):>15.2f}")
        print(f"{'R²(train):':<25} {metrics.get('train_r2', 'N/A'):>15.3f}")
        print(f"{'=' * 40}")
    
    if csv_path:
        print(f"\nПрогноз сохранён: {csv_path}")
    
    if forecast is not None:
        print(f"\nПериод прогноза:")
        print(f"   С: {forecast['datetime'].min()}")
        print(f"   По: {forecast['datetime'].max()}")
        print(f"   Всего часов: {len(forecast)}")
        print(f"   Всего заказов: {forecast['orders_predicted'].sum()}")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    # main()
    main(
        process_data=False,
        train_model=True,
        from_date='2026-04-01',
        to_date='2026-05-01'
    )
    # main(
    #     process_data=False,
    #     train_model=False,
    #     hours_ahead=336
    # )
    # main(train_model=False, make_forecast=False)
    # main(process_data=False, make_forecast=False)
    # main(process_data=False, train_model=False)