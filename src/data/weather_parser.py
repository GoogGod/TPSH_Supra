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
                'temperature_mean': data['daily']['temperature_2m_mean'],
                'temperature_max': data['daily']['temperature_2m_max'],
                'temperature_min': data['daily']['temperature_2m_min'],
                'precipitation': data['daily']['precipitation_sum'],
                'wind_speed': data['daily']['wind_speed_10m_mean'],
                'weather_code': data['daily']['weather_code']
            })
            
            df = self._add_weather_features(df)
            
            if verbose:
                print(f"Получено {len(df)} записей о погоде")
            
            return df
            
        except requests.RequestException as e:
            print(f"Ошибка при запросе погоды: {e}")
            return self._generate_fallback_weather(start_date, end_date)
    
    def _add_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
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
        
        month = dates.month
        base_temp = np.where(
            month.isin([12, 1, 2]), -10,
            np.where(month.isin([3, 4, 5]), 5,
            np.where(month.isin([6, 7, 8]), 22, 8))
        )
        
        df = pd.DataFrame({
            'date': dates,
            'temperature_mean': base_temp + np.random.normal(0, 5, n_days),
            'temperature_max': base_temp + np.random.normal(2, 4, n_days),
            'temperature_min': base_temp + np.random.normal(-3, 4, n_days),
            'precipitation': np.random.exponential(2, n_days),
            'wind_speed': np.random.exponential(5, n_days),
            'weather_code': np.random.choice([0, 1, 2, 3, 61, 71, 95], n_days, 
                                            p=[0.3, 0.25, 0.15, 0.1, 0.1, 0.05, 0.05])
        })
        
        return self._add_weather_features(df)


def merge_weather_with_orders(
    orders_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    verbose: bool = True
) -> pd.DataFrame:
    df = orders_df.copy()
    
    df['order_date'] = pd.to_datetime(df['order_datetime']).dt.date
    
    weather_df = weather_df.copy()
    weather_df['order_date'] = weather_df['date'].dt.date
    
    df_merged = df.merge(
        weather_df.drop(columns=['date']),
        on='order_date',
        how='left'
    )
    
    df_merged = df_merged.drop(columns=['order_date'])
    
    if verbose:
        missing_weather = df_merged['temperature_mean'].isnull().sum()
        print(f"Объединено: {len(df_merged)} записей")
        print(f"Записей без погоды: {missing_weather}")
    
    return df_merged