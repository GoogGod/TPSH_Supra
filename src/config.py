from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = f'{ROOT_DIR}/data/raw'
DATA_PROC_DIR = f'{ROOT_DIR}/data/processed'
DATA_PRED_DIR = f'{ROOT_DIR}/data/predicted'
DATA_RAW_NEW_DIR = f'{ROOT_DIR}/data/raw_new'
MODEL_DIR = f'{ROOT_DIR}/models'
REPORTS_DIR = f'{ROOT_DIR}/reports'

RAW_EXCEL_FILE = f'{DATA_RAW_DIR}/real_orders.xlsx'
RAW_DATA_FILE = f'{DATA_PROC_DIR}/processed_orders.csv'
MODEL_FILE = f'{MODEL_DIR}/model_orders.pkl'
FORECAST_CSV_FILE = f'{DATA_PRED_DIR}/forecast.csv'
RAW_NEW_EXCEL_FILE = f'{DATA_RAW_NEW_DIR}/new_orders.xlsx'

MODEL_PARAMS = {
    'xgboost': {
        'n_estimators': 1000,
        'max_depth': 6,
        'learning_rate': 0.01,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1
    },
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
    'hour_encoded_cos',
    'is_peak_hour',
    'is_lunch_peak',
    'is_dinner_peak',
    'day_of_week',
    'month',
    'day_of_month',
    'week_of_month',
    'week_of_year',
    'quarter',
    'is_weekend',
    'is_month_start',
    'is_month_end',
    'is_quarter_start',
    'is_quarter_end',
    'is_holiday',
    'is_valentine',
    'is_new_year_week',
    'is_march_8',
    'is_may_holidays',
    'is_june_holiday',
    'is_november_holiday',
    'is_december_holidays',
    'is_winter',
    'is_spring',
    'is_summer',
    'is_autumn',
    'hour_weekend',
    'hour_holiday',
    'peak_weekend',
    'peak_holiday',
    'friday_dinner',
    'saturday_dinner',
    'sunday_dinner',
    'saturday_lunch',
    'sunday_lunch',
    'lag_orders_1h',
    'lag_orders_2h',
    'lag_orders_3h',
    'lag_orders_24h',
    'lag_orders_48h',
    'lag_orders_168h',
    'lag_orders_336h',
    'lag_guests_1h',
    'lag_guests_24h',
    'lag_guests_168h',
    'rolling_mean_3h',
    'rolling_mean_6h',
    'rolling_mean_12h',
    'rolling_mean_24h',
    'rolling_mean_168h',
    'rolling_std_3h',
    'rolling_std_24h',
    'rolling_std_168h',
    'rolling_max_24h',
    'rolling_max_168h',
    'rolling_max_720h',
    'deviation_from_mean_24h',
    'deviation_from_mean_168h',
    'is_high_demand',
    'is_very_high_demand',
    'trend',
    'temperature_mean',
    'precipitation',
    'is_rainy',
    'is_extreme_weather',
    'rainy_peak',
    'extreme_peak',
    'cold_weekend',
    'warm_weekend',
]

TARGET_COLUMN = 'orders_count'

TEST_SIZE = 0.2
RANDOM_STATE = 42

# Настройки
WORKING_HOUR_START = 10
WORKING_HOUR_END = 23
MIN_ORDERS_PER_HOUR = 1
MIN_GUESTS_PER_HOUR = 1
MIN_WAITERS_ABSOLUTE = 5
AVG_GUESTS_PER_ORDER = 2.03
MIN_WAITERS_PER_SHIFT = 5
WEATHER_LATITUDE = 43.1056
WEATHER_LONGITUDE = 131.8735