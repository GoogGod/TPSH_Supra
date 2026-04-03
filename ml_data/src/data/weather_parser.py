import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import time
import logging
import os

logger = logging.getLogger(__name__)


class WeatherParser:
    def __init__(self, latitude: float = 43.1056, longitude: float = 131.8735):
        self.latitude = latitude
        self.longitude = longitude
        self.forecast_url = "https://api.open-meteo.com/v1/forecast"
        self.archive_url = "https://archive-api.open-meteo.com/v1/archive"
        
    def get_weather_for_date_range(
        self,
        start_date: str,
        end_date: str,
        verbose: bool = True,
        use_forecast: Optional[bool] = None
    ) -> pd.DataFrame:
        try:
            start_dt = pd.to_datetime(start_date).normalize()
            end_dt = pd.to_datetime(end_date).normalize()
            today = pd.Timestamp.today().normalize()

            if verbose:
                print(f"Запрос погоды: {start_date} — {end_date}")
                print(f"Сегодня: {today.date()}")

            # Случай 1: Только прошлое
            if end_dt <= today:
                if verbose:
                    print("Используем архивный API (только прошлые даты)")
                return self._get_archive_weather(start_date, end_date, verbose)

            # Случай 2: Только будущее
            if start_dt >= today:
                if verbose:
                    print("Используем прогнозный API (только будущие даты)")
                return self._get_forecast_weather(start_date, end_date, verbose)

            # Случай 3: Смешанный период (прошлое + будущее)
            if verbose:
                print("Смешанный период: разделяем на архив + прогноз")
                future_start = today.strftime('%Y-%m-%d')
                df_future = self._get_forecast_weather(future_start, end_date, verbose=False)

            # Прошлая часть: start_date до вчера
            past_end = (today - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            df_past = self._get_archive_weather(start_date, past_end, verbose=False)

            # Будущая часть: сегодня до end_date
            future_start = today.strftime('%Y-%m-%d')
            df_future = self._get_forecast_weather(future_start, end_date, verbose=False)

            # Объединение
            df_combined = pd.concat([df_past, df_future], ignore_index=True)
            df_combined = df_combined.sort_values('date').reset_index(drop=True)

            if verbose:
                print(f"Объединено: {len(df_past)} архив + {len(df_future)} прогноз = {len(df_combined)} записей")

            return df_combined

        except Exception as e:
            if verbose:
                print(f"Ошибка при загрузке погоды: {type(e).__name__}: {e}")
            return self._generate_fallback_weather(start_date, end_date, verbose)

        except Exception as e:
            if verbose:
                print(f"Ошибка при загрузке погоды: {type(e).__name__}: {e}")
            return self._generate_fallback_weather(start_date, end_date, verbose)
    
    def _get_forecast_weather(
        self,
        start_date: str,
        end_date: str,
        verbose: bool = True
    ) -> pd.DataFrame:
    # Open-Meteo forecast API поддерживает максимум 16 дней вперёд
        MAX_FORECAST_DAYS = 16
        today = pd.Timestamp.today().normalize()
        max_forecast_date = (today + pd.Timedelta(days=MAX_FORECAST_DAYS)).normalize()

        start_dt = pd.to_datetime(start_date).normalize()
        end_dt = pd.to_datetime(end_date).normalize()

        # Проверка: если период полностью за пределами прогноза
        if start_dt > max_forecast_date:
            if verbose:
                print(f"Период {start_date} — {end_date} за пределами прогноза (макс. {max_forecast_date.date()})")
                print("Использую резервные погодные данные")
            return self._generate_fallback_weather(start_date, end_date, verbose=False)

        # Обрезаем end_date до максимума, если нужно
        actual_end_date = min(end_dt, max_forecast_date).strftime('%Y-%m-%d')

        if verbose and actual_end_date != end_date:
            print(f"Прогноз доступен только до {actual_end_date}, остальное — резервные данные")

        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_date': start_date,
            'end_date': actual_end_date,
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
            print(f"Запрос прогноза погоды: {start_date} — {actual_end_date}")

        try:
            response = requests.get(self.forecast_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'daily' not in data or 'time' not in data['daily']:
                raise ValueError("API вернул некорректный формат данных")

            df = pd.DataFrame({
                'date': pd.to_datetime(data['daily']['time']),
                'temperature_mean': data['daily'].get('temperature_2m_mean'),
                'temperature_max': data['daily'].get('temperature_2m_max'),
                'temperature_min': data['daily'].get('temperature_2m_min'),
                'precipitation': data['daily'].get('precipitation_sum'),
                'wind_speed': data['daily'].get('wind_speed_10m_mean'),
                'weather_code': data['daily'].get('weather_code')
            })

            df['weather_source'] = 'forecast'
            df = self._clean_and_add_features(df)

        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                if verbose:
                    print(f"API ошибка 400: период за пределами доступного прогноза")
                    print(f"Максимальная дата прогноза: {max_forecast_date.date()}")
                # Возвращаем фоллбэк для всего запрошенного периода
                return self._generate_fallback_weather(start_date, end_date, verbose=False)
            raise
        
        # Если запрашивали больше, чем доступно в прогнозе — добавляем фоллбэк для остатка
        if end_dt > max_forecast_date:
            if verbose:
                print(f"Добавляю резервные данные для {max_forecast_date.date()} — {end_dt.date()}")

            fallback_start = (max_forecast_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            fallback_end = end_date
            df_fallback = self._generate_fallback_weather(fallback_start, fallback_end, verbose=False)

            df = pd.concat([df, df_fallback], ignore_index=True)
            df = df.sort_values('date').reset_index(drop=True)

        if verbose:
            print(f"Получено {len(df)} записей погоды (прогноз + резерв)")

        return df
    
    def _get_archive_weather(
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
            print(f"Запрос архивной погоды: {start_date} — {end_date}")
        
        response = requests.get(self.archive_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'daily' not in data or 'time' not in data['daily']:
            raise ValueError("API вернул некорректный формат данных")
        
        df = pd.DataFrame({
            'date': pd.to_datetime(data['daily']['time']),
            'temperature_mean': data['daily'].get('temperature_2m_mean'),
            'temperature_max': data['daily'].get('temperature_2m_max'),
            'temperature_min': data['daily'].get('temperature_2m_min'),
            'precipitation': data['daily'].get('precipitation_sum'),
            'wind_speed': data['daily'].get('wind_speed_10m_mean'),
            'weather_code': data['daily'].get('weather_code')
        })
        
        df['weather_source'] = 'archive'
        df = self._clean_and_add_features(df)
        
        if verbose:
            print(f"Получено {len(df)} записей архивной погоды")
        
        return df
    
    def _clean_and_add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        numeric_cols = ['temperature_mean', 'temperature_max', 'temperature_min', 
                       'precipitation', 'wind_speed']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].fillna(df[col].median() if df[col].notna().any() else 0)
            else:
                df[col] = 0.0
        
        if 'weather_code' in df.columns:
            df['weather_code'] = pd.to_numeric(df['weather_code'], errors='coerce').fillna(0)
        else:
            df['weather_code'] = 0
        
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
    
    def _decode_weather_code(self, code) -> str:
        if pd.isna(code):
            return 'неизвестно'
        code = int(code)
        codes = {
            0: 'ясно', 1: 'преимущественно_ясно', 2: 'переменная_облачность',
            3: 'пасмурно', 45: 'туман', 48: 'иней',
            51: 'слабая_морось', 53: 'умеренная_морось', 55: 'сильная_морось',
            61: 'слабый_дождь', 63: 'умеренный_дождь', 65: 'сильный_дождь',
            71: 'слабый_снег', 73: 'умеренный_снег', 75: 'сильный_снег',
            77: 'снежные_зерна', 80: 'слабый_ливень', 81: 'умеренный_ливень',
            82: 'сильный_ливень', 95: 'гроза', 96: 'гроза_с_градом',
            99: 'сильная_гроза_с_градом'
        }
        return codes.get(code, 'неизвестно')
    
    def _get_temp_comfort(self, temp) -> str:
        if pd.isna(temp):
            return 'неизвестно'
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
            print("Генерация резервных погодных данных для Владивостока")

        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        n_days = len(dates)

        if n_days == 0:
            return self._create_empty_weather_df()

        # Климатические нормы Владивостока по месяцам
        climate_norms = {
            1: {'temp': -12, 'precip': 15, 'wind': 5},
            2: {'temp': -10, 'precip': 12, 'wind': 5},
            3: {'temp': -3, 'precip': 18, 'wind': 6},
            4: {'temp': 6, 'precip': 25, 'wind': 5},
            5: {'temp': 13, 'precip': 45, 'wind': 4},
            6: {'temp': 18, 'precip': 70, 'wind': 4},
            7: {'temp': 21, 'precip': 120, 'wind': 3},
            8: {'temp': 22, 'precip': 140, 'wind': 3},
            9: {'temp': 17, 'precip': 90, 'wind': 4},
            10: {'temp': 10, 'precip': 50, 'wind': 5},
            11: {'temp': 1, 'precip': 25, 'wind': 6},
            12: {'temp': -8, 'precip': 18, 'wind': 5},
        }

        # Детерминированный seed для воспроизводимости
        np.random.seed(hash(f"{start_date}_{end_date}_{self.latitude}_{self.longitude}") % 2**32)

        months = dates.month
        base_temp = np.array([climate_norms[m]['temp'] for m in months])
        base_precip = np.array([climate_norms[m]['precip'] for m in months])
        base_wind = np.array([climate_norms[m]['wind'] for m in months])

        # ТЕМПЕРАТУРА: больше случайных отклонений
        # Добавляем: суточные колебания + случайные аномалии + тренд
        daily_variation = np.random.normal(0, 5, n_days)  # Увеличено с 4 до 5
        anomaly_mask = np.random.random(n_days) < 0.1  # 10% дней с аномалиями
        temperature_anomalies = np.zeros(n_days)
        temperature_anomalies[anomaly_mask] = np.random.choice([-8, -6, 6, 8], anomaly_mask.sum())

        # Плавный тренд внутри периода (имитация изменения погоды)
        trend = np.linspace(-2, 2, n_days) * np.random.random()

        temperature_mean = base_temp + daily_variation + temperature_anomalies + trend
        temperature_max = temperature_mean + np.random.uniform(3, 8, n_days)
        temperature_min = temperature_mean - np.random.uniform(3, 8, n_days)

        # ОСАДКИ: больше вариативности
        # Разные типы дней: сухо, моросящий дождь, ливень
        day_types = np.random.choice(
            ['dry', 'light_rain', 'rain', 'heavy_rain'],
            n_days,
            p=[0.50, 0.25, 0.15, 0.10]  # 50% сухо, 25% слабый, 15% средний, 10% сильный
        )

        precipitation = np.zeros(n_days)
        precipitation[day_types == 'light_rain'] = np.random.uniform(0.5, 3, (day_types == 'light_rain').sum())
        precipitation[day_types == 'rain'] = np.random.uniform(3, 10, (day_types == 'rain').sum())
        precipitation[day_types == 'heavy_rain'] = np.random.uniform(10, 30, (day_types == 'heavy_rain').sum())

        # ВЕТЕР: больше диапазонов
        wind_base = base_wind + np.random.normal(0, 2, n_days)
        wind_gust_mask = np.random.random(n_days) < 0.15  # 15% дней с порывами
        wind_speed = np.abs(wind_base)
        wind_speed[wind_gust_mask] += np.random.uniform(5, 12, wind_gust_mask.sum())
        wind_speed = np.clip(wind_speed, 0.5, 25)  # Ограничение реалистичными значениями

        # ПОГОДНЫЕ КОДЫ: больше разнообразия
        weather_code = np.zeros(n_days, dtype=int)

        # Ясно (0-1)
        clear_mask = (day_types == 'dry') & (wind_speed < 8)
        weather_code[clear_mask] = np.random.choice([0, 1], clear_mask.sum())

        # Облачно (2-3)
        cloudy_mask = (day_types == 'dry') & (wind_speed >= 8)
        weather_code[cloudy_mask] = np.random.choice([2, 3], cloudy_mask.sum())

        # Дождь (61-65, 80-82)
        rain_mask = day_types == 'light_rain'
        weather_code[rain_mask] = np.random.choice([61, 63, 80], rain_mask.sum())

        rain_mask = day_types == 'rain'
        weather_code[rain_mask] = np.random.choice([63, 65, 81], rain_mask.sum())

        rain_mask = day_types == 'heavy_rain'
        weather_code[rain_mask] = np.random.choice([65, 82, 95], rain_mask.sum())

        # Снег (если температура < 0)
        snow_mask = (temperature_mean < 0) & (precipitation > 0.5)
        weather_code[snow_mask] = np.random.choice([71, 73, 75], snow_mask.sum())

        df = pd.DataFrame({
            'date': dates,
            'temperature_mean': temperature_mean,
            'temperature_max': temperature_max,
            'temperature_min': temperature_min,
            'precipitation': precipitation,
            'wind_speed': wind_speed,
            'weather_code': weather_code,
            'weather_source': 'fallback'  # Метка источника
        })

        return self._clean_and_add_features(df)
    
    def _create_empty_weather_df(self) -> pd.DataFrame:
        return pd.DataFrame(columns=[
            'date', 'temperature_mean', 'temperature_max', 'temperature_min',
            'precipitation', 'wind_speed', 'weather_code',
            'is_rainy', 'is_snowy', 'weather_category', 
            'temp_comfort', 'is_extreme_weather'
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
    
    weather_cols = ['date', 'temperature_mean', 'precipitation', 
                   'is_rainy', 'is_extreme_weather']
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