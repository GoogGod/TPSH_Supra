from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = f'{ROOT_DIR}/data/raw'
DATA_PROC_DIR = f'{ROOT_DIR}/data/processed'
DATA_PRED_DIR = f'{ROOT_DIR}/data/predicted'
MODEL_DIR = f'{ROOT_DIR}/models'
REPORTS_DIR = f'{ROOT_DIR}/reports'

# Пути к файлам
RAW_EXCEL_FILE = f'{DATA_RAW_DIR}/real_orders.xlsx'
RAW_DATA_FILE = f'{DATA_PROC_DIR}/processed_orders.csv'  
MODEL_FILE = f'{MODEL_DIR}/waiter_staffing_model.pkl'
FORECAST_CSV_FILE = f'{DATA_PRED_DIR}/predicted.csv'

# Параметры модели
MODEL_PARAMS = {
    'random_forest': {
        'n_estimators': 500,
        'max_depth': 15,
        'min_samples_split': 5,
        'min_samples_leaf': 3,
        'max_features': 'sqrt',
        'bootstrap': True,
        'oob_score': True,
        'random_state': 42,
        'n_jobs': -1
    },
    'gradient_boosting': {
        'n_estimators': 2000,
        'max_depth': 6,
        'min_samples_split': 10,
        'min_samples_leaf': 5,
        'learning_rate': 0.01,
        'subsample': 0.8,
        'max_features': 'sqrt',
        'random_state': 42
    }
}

FEATURE_COLS = [
    'hour_encoded',
    'is_peak_hour',
    'is_lunch_peak',
    'is_dinner_peak',
    
    'day_of_week',
    'month',
    'day_of_month',
    'is_weekend',
    'is_month_start',
    'is_month_end',
    'is_holiday',
    
    'hour_weekend',
    'hour_holiday',
    'peak_weekend',
    'peak_holiday',
    'friday_dinner',
    'saturday_dinner',
    'sunday_dinner',
    
    'lag_orders_1block',
    'lag_orders_1day',
    'lag_orders_1week',
    'rolling_mean_3blocks',
    'rolling_mean_1day',
    'rolling_std_1day',
    
    'temperature_mean',
    'precipitation',
    'is_rainy',
    'is_extreme_weather',
    'rainy_peak',
    'extreme_peak',
]

TARGET_COLUMN = 'orders_count'

ORDERS_PER_WAITER = 12
TEST_SIZE = 0.2
RANDOM_STATE = 42

# Координаты Владивостока
WEATHER_CONFIG = {
    'enabled': True,
    'location': {
        'latitude': 43.1056,
        'longitude': 131.8735
    },
    'features': [
        'temperature_mean',
        'precipitation',
        'wind_speed',
        'is_rainy',
        'is_extreme_weather'
    ]
}

WORKING_HOUR_START = 10
WORKING_HOUR_END = 23
MIN_ORDERS_PER_HOUR = 1
AVG_GUESTS_PER_ORDER = 2.3