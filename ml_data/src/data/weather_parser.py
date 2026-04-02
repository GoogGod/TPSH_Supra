import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import time


class WeatherParser:
    def __init__(self, latitude: float = 43.1056, longitude: float = 131.8735):
        self.latitude = latitude
        self.longitude = longitude
        self.base_url = "https://archive-api.open-meteo.com/v1/archive"
        
    def get_weather_for_date_range(
        self,
        start_date: str,
        end_date: str,
        verbose: bool = True
    ) -> pd.DataFrame:
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_date': start_date,
            'end_date': end_date,
            'timezone': 'Asia/Vladivostok',
            'daily': [
                'temperature_2m_mean',
                'temperature_2m_max',
                'temperature_2m_min',
                'precipitation_sum',
                'wind_speed_10m_mean',
                'weather_code'
            ]
        }
        
        if verbose:
            print(f"Запрос погоды для Владивостока: {start_date} — {end_date}")
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            df = pd.DataFrame({
                'date': pd.to_datetime(data['daily']['time']),
                'temperature_mean': data['daily'].get('temperature_2m_mean', [None]*len(data['daily']['time'])),
                'temperature_max': data['daily'].get('temperature_2m_max', [None]*len(data['daily']['time'])),
                'temperature_min': data['daily'].get('temperature_2m_min', [None]*len(data['daily']['time'])),
                'precipitation': data['daily'].get('precipitation_sum', [None]*len(data['daily']['time'])),
                'wind_speed': data['daily'].get('wind_speed_10m_mean', [None]*len(data['daily']['time'])),
                'weather_code': data['daily'].get('weather_code', [None]*len(data['daily']['time']))
            })
            
            df = self._add_weather_features(df)
            
            if verbose:
                print(f"Получено {len(df)} записей о погоде")
            
            return df
            
        except requests.RequestException as e:
            print(f"Ошибка при запросе погоды: {e}")
            return self._generate_fallback_weather(start_date, end_date, verbose)
    
    def _add_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        for col in ['temperature_mean', 'precipitation', 'wind_speed', 'weather_code']:
            if col not in df.columns:
                df[col] = 0.0
        
        df['is_rainy'] = (df['precipitation'] > 0.5).astype(int)
        df['is_snowy'] = ((df['temperature_mean'] < 0) & (df['precipitation'] > 0.5)).astype(int)
        
        df['weather_category'] = df['weather_code'].apply(self._decode_weather_code)
        df['temp_comfort'] = df['temperature_mean'].apply(self._get_temp_comfort)
        
        df['is_extreme_weather'] = (
            (df['temperature_mean'] < -15) | 
            (df['temperature_mean'] > 30) | 
            (df['wind_speed'] > 15) |
            (df['precipitation'] > 20)
        ).astype(int)
        
        return df
    
    def _decode_weather_code(self, code: int) -> str:
        codes = {
            0: 'ясно',
            1: 'преимущественно_ясно',
            2: 'переменная_облачность',
            3: 'пасмурно',
            45: 'туман',
            48: 'иней',
            51: 'слабая_морось',
            53: 'умеренная_морось',
            55: 'сильная_морось',
            61: 'слабый_дождь',
            63: 'умеренный_дождь',
            65: 'сильный_дождь',
            71: 'слабый_снег',
            73: 'умеренный_снег',
            75: 'сильный_снег',
            77: 'снежные_зерна',
            80: 'слабый_ливень',
            81: 'умеренный_ливень',
            82: 'сильный_ливень',
            95: 'гроза',
            96: 'гроза_с_градом',
            99: 'сильная_гроза_с_градом'
        }
        return codes.get(code, 'неизвестно')
    
    def _get_temp_comfort(self, temp: float) -> str:
        if temp < -10:
            return 'очень_холодно'
        elif temp < 0:
            return 'холодно'
        elif temp < 10:
            return 'прохладно'
        elif temp < 20:
            return 'комфортно'
        elif temp < 28:
            return 'тепло'
        else:
            return 'жарко'
    
    def _generate_fallback_weather(
        self,
        start_date: str,
        end_date: str,
        verbose: bool = True
    ) -> pd.DataFrame:
        if verbose:
            print("API недоступен, генерирую реалистичные погодные данные для Владивостока")
        
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        n_days = len(dates)
        
        if n_days == 0:
            return self._create_empty_weather_df()
        
        climate_norms = {
            1: {'temp': -12, 'precip': 15}, 2: {'temp': -10, 'precip': 12},
            3: {'temp': -3, 'precip': 18}, 4: {'temp': 6, 'precip': 25},
            5: {'temp': 13, 'precip': 45}, 6: {'temp': 18, 'precip': 70},
            7: {'temp': 21, 'precip': 120}, 8: {'temp': 22, 'precip': 140},
            9: {'temp': 17, 'precip': 90}, 10: {'temp': 10, 'precip': 50},
            11: {'temp': 1, 'precip': 25}, 12: {'temp': -8, 'precip': 18},
        }
        
        np.random.seed(42)
        months = dates.month
        base_temp = np.array([climate_norms[m]['temp'] for m in months])
        base_precip = np.array([climate_norms[m]['precip'] for m in months])
        
        temperature_mean = base_temp + np.random.normal(0, 4, n_days)
        precipitation = np.zeros(n_days)
        rainy_mask = np.random.random(n_days) < 0.35
        precipitation[rainy_mask] = np.random.exponential(
            base_precip[rainy_mask] / 0.35 / 30, rainy_mask.sum()
        )
        wind_speed = np.random.exponential(4, n_days)
        weather_code = np.zeros(n_days, dtype=int)
        
        df = pd.DataFrame({
            'date': dates,
            'temperature_mean': temperature_mean,
            'temperature_max': temperature_mean + np.random.uniform(2, 6, n_days),
            'temperature_min': temperature_mean - np.random.uniform(2, 6, n_days),
            'precipitation': precipitation,
            'wind_speed': wind_speed,
            'weather_code': weather_code
        })
        
        return self._add_weather_features(df)
    
    def _create_empty_weather_df(self) -> pd.DataFrame:
        return pd.DataFrame(columns=[
            'date', 'temperature_mean', 'temperature_max', 'temperature_min',
            'precipitation', 'wind_speed', 'weather_code',
            'is_rainy', 'is_snowy', 'is_extreme_weather'
        ])


def merge_weather_with_orders(
    orders_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    verbose: bool = True
) -> pd.DataFrame:
    if weather_df is None or weather_df.empty:
        for col in ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']:
            orders_df[col] = 0
        orders_df['rainy_peak'] = 0
        orders_df['extreme_peak'] = 0
        return orders_df
    
    df = orders_df.copy()
    df['order_date'] = pd.to_datetime(df['datetime']).dt.date
    weather_df = weather_df.copy()
    weather_df['order_date'] = pd.to_datetime(weather_df['date']).dt.date
    
    weather_cols = ['date', 'temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']
    available_cols = [c for c in weather_cols if c in weather_df.columns]
    
    if len(available_cols) < 2:
        for col in ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']:
            df[col] = 0
        df['rainy_peak'] = 0
        df['extreme_peak'] = 0
        return df.drop(columns=['order_date'], errors='ignore')
    
    df_merged = df.merge(
        weather_df[available_cols].drop_duplicates('order_date'),
        on='order_date',
        how='left'
    )
    
    for col in ['temperature_mean', 'precipitation', 'is_rainy', 'is_extreme_weather']:
        if col in df_merged.columns:
            if df_merged[col].notna().any():
                df_merged[col] = df_merged[col].fillna(df_merged[col].median())
            else:
                df_merged[col] = 0
        else:
            df_merged[col] = 0
    
    if 'is_peak_hour' in df_merged.columns:
        df_merged['rainy_peak'] = df_merged['is_rainy'] * df_merged['is_peak_hour']
        df_merged['extreme_peak'] = df_merged['is_extreme_weather'] * df_merged['is_peak_hour']
    else:
        df_merged['rainy_peak'] = 0
        df_merged['extreme_peak'] = 0
    
    return df_merged.drop(columns=['order_date'], errors='ignore')