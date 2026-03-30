import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
from pathlib import Path
from typing import Tuple, Dict


# КОНФИГУРАЦИЯ

WAITER_TYPES = {
    'specialist': {
        'name': 'Специалист',
        'capacity': 10,  # гостей в час
        'code': 1
    },
    'novice': {
        'name': 'Новичок',
        'capacity': 5,   # гостей в час
        'code': 2
    }
}

SHIFT_TYPES = {
    'full': {
        'name': 'Полная',
        'start': 10,
        'end': 22,    
        'hours': 12,
        'code': 1
    },
    'morning': {
        'name': 'Утренняя',
        'start': 10,
        'end': 16,
        'hours': 6,      
        'code': 2
    },
    'evening': {
        'name': 'Вечерняя',
        'start': 16,
        'end': 25,      
        'hours': 9,
        'code': 3
    },
    'off': {
        'name': 'Выходной',
        'start': None,
        'end': None,
        'hours': 0,
        'code': 0
    }
}

# Минимальная выработка в месяц (часов)
MIN_HOURS_PER_MONTH = 200


class WaiterScheduler:
    def __init__(
        self,
        min_waiters_per_shift: int = 1,
        max_work_hours_per_week: int = 48,
        min_days_off_per_week: int = 1
    ):
        self.min_waiters_per_shift = min_waiters_per_shift
        self.max_work_hours_per_week = max_work_hours_per_week
        self.min_days_off_per_week = min_days_off_per_week
        
        self.working_hour_start = 10
        self.working_hour_end = 23
    
    def calculate_waiters_needed(
        self, 
        forecast_df: pd.DataFrame,
        waiter_config: Dict[int, str]
    ) -> pd.DataFrame:
        df = forecast_df.copy()
        
        # Конвертируем гостей в "эквивалентных новичков" (1 специалист = 2 новичка)
        # Это позволяет планировать смешанные бригады
        df['waiters_equiv_novice'] = np.ceil(
            df['guests_with_buffer'] / WAITER_TYPES['novice']['capacity']
        ).astype(int)
        
        # Минимум 1 официант в рабочие часы
        working_mask = (df['hour'] >= self.working_hour_start) & \
                       (df['hour'] < self.working_hour_end)
        df.loc[working_mask, 'waiters_equiv_novice'] = df.loc[
            working_mask, 'waiters_equiv_novice'
        ].clip(lower=self.min_waiters_per_shift)
        
        # Вне рабочих часов — 0
        df.loc[~working_mask, 'waiters_equiv_novice'] = 0
        
        return df
    
    def calculate_daily_shift_requirements(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['date'] = pd.to_datetime(df['datetime']).dt.date
        
        daily_hourly = df.groupby(['date', 'hour'])['waiters_equiv_novice'].max().reset_index()
        
        daily_requirements = []
        
        for date in df['date'].unique():
            day_data = daily_hourly[daily_hourly['date'] == date]
            
            # Утренний период (10:00-15:00) — обеденный пик
            morning_hours = day_data[(day_data['hour'] >= 10) & (day_data['hour'] < 16)]
            morning_need = int(morning_hours['waiters_equiv_novice'].max()) if len(morning_hours) > 0 else 0
            
            # Вечерний период (16:00-22:00) — ужинный пик
            evening_hours = day_data[(day_data['hour'] >= 16) & (day_data['hour'] < 23)]
            evening_need = int(evening_hours['waiters_equiv_novice'].max()) if len(evening_hours) > 0 else 0
            
            daily_requirements.append({
                'date': date,
                'morning_need': morning_need,
                'evening_need': evening_need,
                'total_waiters_needed': max(morning_need, evening_need)
            })
        
        return pd.DataFrame(daily_requirements)
    
    def create_schedule(
        self,
        forecast_df: pd.DataFrame,
        waiter_config: Dict[int, str],
        verbose: bool = True
    ) -> Tuple[pd.DataFrame, Dict]:
        if verbose:
            print("ПЛАНИРОВАНИЕ СМЕН ОФИЦИАНТОВ")
        
        # Рассчитываем потребность
        df = self.calculate_waiters_needed(forecast_df, waiter_config)
        daily_req = self.calculate_daily_shift_requirements(df)
        
        num_days = len(daily_req)
        date_list = daily_req['date'].tolist()
        num_waiters = len(waiter_config)
        
        if verbose:
            print(f"\nПериод планирования: {num_days} дней (~{num_days/30*100:.0f}% месяца)")
            print(f"Количество официантов: {num_waiters}")
            print(f"Типы официантов:")
            for w, t in waiter_config.items():
                cap = WAITER_TYPES[t]['capacity']
                print(f"   Официант {w}: {WAITER_TYPES[t]['name']} ({cap} гостей/час)")
            print(f"Типы смен: Полная (10-23), Утренняя (10-16), Вечерняя (16-23)")
            print(f"Минимальная выработка: {MIN_HOURS_PER_MONTH} часов/месяц")
        
        # Рассчитываем реальную потребность в часах
        total_guest_hours = df[df['guests_with_buffer'] > 0]['guests_with_buffer'].sum()
        avg_capacity = np.mean([WAITER_TYPES[t]['capacity'] for t in waiter_config.values()])
        estimated_total_hours = int(np.ceil(total_guest_hours / avg_capacity))
        
        # Адаптивная минимальная выработка:
        # Если потребность низкая — снижаем требование пропорционально
        min_hours_per_waiter = int(MIN_HOURS_PER_MONTH * num_days / 30)
        
        # Максимально возможное распределение часов
        max_possible_hours = estimated_total_hours
        min_required_total = min_hours_per_waiter * num_waiters
        
        # Если требование превышает возможное — снижаем пропорционально
        if min_required_total > max_possible_hours * 1.5:  # 50% запас
            scale_factor = (max_possible_hours * 1.5) / min_required_total
            min_hours_per_waiter = int(min_hours_per_waiter * scale_factor)
            if verbose:
                print(f"\nПотребность низкая — мин. выработка снижена:")
                print(f"   Было: {int(MIN_HOURS_PER_MONTH * num_days / 30)}ч")
                print(f"   Стало: {min_hours_per_waiter}ч (масштаб: {scale_factor:.2f})")
        
        # Целевое количество часов (не ниже минимума)
        target_hours = max(min_hours_per_waiter, estimated_total_hours // num_waiters)
        
        if verbose:
            print(f"\nЦелевые показатели:")
            print(f"   Общая потребность: ~{estimated_total_hours} часов")
            print(f"   Минимум часов/официант: {min_hours_per_waiter}")
            print(f"   Целевое часов/официант: ~{target_hours}")
        
        model = cp_model.CpModel()
        
        # ПЕРЕМЕННЫЕ
        
        shift = {}
        for w in range(1, num_waiters + 1):
            for d in range(num_days):
                for s in [1, 2, 3]:
                    shift[(w, d, s)] = model.NewBoolVar(f'shift_w{w}_d{d}_s{s}')
        
        waiter_hours = {}
        for w in range(1, num_waiters + 1):
            waiter_hours[w] = model.NewIntVar(0, num_days * 13, f'hours_w{w}')
            
            hour_expr = sum(
                SHIFT_TYPES['full']['hours'] * shift[(w, d, 1)] +
                SHIFT_TYPES['morning']['hours'] * shift[(w, d, 2)] +
                SHIFT_TYPES['evening']['hours'] * shift[(w, d, 3)]
                for d in range(num_days)
            )
            model.Add(waiter_hours[w] == hour_expr)
        
        # ОГРАНИЧЕНИЯ
        
        # 1. Одна смена в день
        for w in range(1, num_waiters + 1):
            for d in range(num_days):
                model.Add(sum(shift[(w, d, s)] for s in [1, 2, 3]) <= 1)
        
        # 2. Покрытие потребности
        for d in range(num_days):
            morning_need = daily_req.loc[d, 'morning_need']
            evening_need = daily_req.loc[d, 'evening_need']
            
            morning_coverage = sum(
                (WAITER_TYPES[waiter_config[w]]['capacity'] // WAITER_TYPES['novice']['capacity']) 
                * (shift[(w, d, 2)] + shift[(w, d, 1)])
                for w in range(1, num_waiters + 1)
            )
            model.Add(morning_coverage >= morning_need)
            
            evening_coverage = sum(
                (WAITER_TYPES[waiter_config[w]]['capacity'] // WAITER_TYPES['novice']['capacity'])
                * (shift[(w, d, 3)] + shift[(w, d, 1)])
                for w in range(1, num_waiters + 1)
            )
            model.Add(evening_coverage >= evening_need)
        
        # 3. Минимальная выработка (адаптивная)
        for w in range(1, num_waiters + 1):
            model.Add(waiter_hours[w] >= min_hours_per_waiter)
        
        # 4. Максимум часов в неделю
        for w in range(1, num_waiters + 1):
            for d in range(num_days - 6):
                weekly_hours = sum(
                    SHIFT_TYPES['full']['hours'] * shift[(w, i, 1)] +
                    SHIFT_TYPES['morning']['hours'] * shift[(w, i, 2)] +
                    SHIFT_TYPES['evening']['hours'] * shift[(w, i, 3)]
                    for i in range(d, d + 7)
                )
                model.Add(weekly_hours <= self.max_work_hours_per_week)
        
        # 5. Минимум 1 выходной в 7 дней
        for w in range(1, num_waiters + 1):
            for d in range(num_days - 6):
                model.Add(
                    sum(sum(shift[(w, i, s)] for s in [1, 2, 3]) for i in range(d, d + 7)) <= 6
                )
        
        # ЦЕЛЕВАЯ ФУНКЦИЯ
        
        total_shifts = sum(
            shift[(w, d, s)] for w in range(1, num_waiters + 1) for d in range(num_days) for s in [1, 2, 3]
        )
        
        # Баланс через AddAbsEquality
        imbalance_vars = []
        for w in range(1, num_waiters + 1):
            deviation = model.NewIntVar(0, num_days * 13, f'deviation_w{w}')
            model.AddAbsEquality(deviation, waiter_hours[w] - target_hours)
            imbalance_vars.append(deviation)
        
        total_imbalance = sum(imbalance_vars)
        
        model.Minimize(total_shifts * 10 + total_imbalance)
        
        # РЕШЕНИЕ
        
        if verbose:
            print("\nРешение оптимизационной задачи...")
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 45.0 
        solver.parameters.num_search_workers = 8
        solver.parameters.cp_model_presolve = True
        solver.parameters.linearization_level = 1
        
        status = solver.Solve(model)
        
        # Обработка статусов
        if status == cp_model.OPTIMAL:
            if verbose:
                print(f"OPTIMAL: найдено оптимальное решение")
        elif status == cp_model.FEASIBLE:
            if verbose:
                print(f"FEASIBLE: найдено допустимое решение (не оптимальное)")
        elif status == cp_model.UNKNOWN:
            if verbose:
                print(f"UNKNOWN: время вышло, используется лучшее найденное")
                print(f"Совет: увеличьте max_time_in_seconds или упростите ограничения")
            # Продолжаем с лучшим найденным решением
        else:
            if verbose:
                print(f"{solver.StatusName(status)}: не удалось найти решение")
                print(f"Попробуйте:")
                print(f"   • Уменьшить min_hours_per_waiter (сейчас: {min_hours_per_waiter})")
                print(f"   • Увеличить количество официантов")
                print(f"   • Увеличить max_time_in_seconds")
            return None, {}
        
        # СОЗДАНИЕ РАСПИСАНИЯ
        
        schedule_data = []
        
        for w in range(1, num_waiters + 1):
            waiter_type = waiter_config[w]
            
            for d in range(num_days):
                shift_type_code = 0
                shift_name = 'Выходной'
                work_start = None
                work_end = None
                work_hours = 0
                
                # Словарь для быстрого доступа по коду смены
                SHIFT_INFO = {
                    1: {'name': 'Полная', 'start': 10, 'end': 22, 'hours': 12},
                    2: {'name': 'Утренняя', 'start': 10, 'end': 16, 'hours': 6},
                    3: {'name': 'Вечерняя', 'start': 16, 'end': 25, 'hours': 9},
                }
                
                for s in [1, 2, 3]:
                    if solver.Value(shift[(w, d, s)]) == 1:
                        shift_type_code = s
                        shift_name = SHIFT_INFO[s]['name']
                        work_start = SHIFT_INFO[s]['start']
                        work_end = SHIFT_INFO[s]['end']
                        work_hours = SHIFT_INFO[s]['hours']
                        break
                
                schedule_data.append({
                    'date': date_list[d],
                    'waiter_id': f'Официант {w}',
                    'waiter_num': w,
                    'waiter_type': WAITER_TYPES[waiter_type]['name'],
                    'waiter_type_code': WAITER_TYPES[waiter_type]['code'],
                    'waiter_capacity': WAITER_TYPES[waiter_type]['capacity'],
                    'shift_type_code': shift_type_code,
                    'shift_type': shift_name,
                    'work_start': work_start,
                    'work_end': work_end,
                    'work_hours': work_hours,
                    'waiters_needed': daily_req.loc[d, 'total_waiters_needed']
                })
        
        schedule_df = pd.DataFrame(schedule_data)
        
        # Статистика
        total_assigned = (schedule_df['shift_type_code'] > 0).sum()
        total_hours = schedule_df['work_hours'].sum()
        
        stats = {
            'total_waiters': num_waiters,
            'total_days': num_days,
            'total_shifts': int(total_assigned),
            'total_hours': int(total_hours),
            'full_shifts': int((schedule_df['shift_type_code'] == 1).sum()),
            'morning_shifts': int((schedule_df['shift_type_code'] == 2).sum()),
            'evening_shifts': int((schedule_df['shift_type_code'] == 3).sum()),
            'avg_hours_per_waiter': float(total_hours / num_waiters) if num_waiters > 0 else 0,
            'min_hours_met': bool(schedule_df.groupby('waiter_num')['work_hours'].sum().min() >= min_hours_per_waiter),
            'status': solver.StatusName(status)
        }
        
        if verbose:
            print(f"\nРезультаты:")
            print(f"   Всего смен: {stats['total_shifts']}")
            print(f"     • Полных: {stats['full_shifts']}")
            print(f"     • Утренних: {stats['morning_shifts']}")
            print(f"     • Вечерних: {stats['evening_shifts']}")
            print(f"   Всего часов: {stats['total_hours']}")
            print(f"   Часов на официанта: {stats['avg_hours_per_waiter']:.1f}")
            print(f"   Минимум {min_hours_per_waiter}ч: {'1' if stats['min_hours_met'] else '0'}")
        
        return schedule_df, stats
    
    def print_schedule_summary(self, schedule_df: pd.DataFrame, min_hours: int):        
        # Сначала краткая сводка
        print("КРАТКАЯ СВОДКА РАСПИСАНИЯ")
        
        print("\nПо официантам:")
        waiter_stats = schedule_df.groupby(['waiter_id', 'waiter_type']).agg({
            'shift_type_code': lambda x: (x > 0).sum(),
            'work_hours': 'sum'
        }).reset_index()
        waiter_stats.columns = ['Официант', 'Тип', 'Смен', 'Часов']
        waiter_stats['% от мин.'] = (waiter_stats['Часов'] / min_hours * 100).round(1)
        waiter_stats['Статус'] = waiter_stats['Часов'].apply(
            lambda h: '1' if h >= min_hours else '0'
        )
        print(waiter_stats.to_string(index=False))
        
        print("\nРаспределение типов смен:")
        shift_counts = schedule_df[schedule_df['shift_type_code'] > 0].groupby('shift_type').size()
        for shift_type, count in shift_counts.items():
            print(f"   {shift_type}: {count} смен")
        
        print("\nРаспределение по типам официантов:")
        type_stats = schedule_df[schedule_df['shift_type_code'] > 0].groupby('waiter_type').agg({
            'work_hours': 'sum',
            'shift_type_code': 'count'
        })
        type_stats.columns = ['Часов', 'Смен']
        print(type_stats.to_string())
        
        self.print_waiter_statistics(schedule_df, min_hours)
    
    def export_schedule(
        self,
        schedule_df: pd.DataFrame,
        output_path: str = None,
        format: str = 'csv',
        verbose: bool = True
    ) -> str:
        if output_path is None:
            output_path = Path('data/predicted/waiter_schedule.csv')
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'csv':
            schedule_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        elif format == 'excel':
            schedule_df.to_excel(output_path.with_suffix('.xlsx'), index=False)
        elif format == 'json':
            schedule_df.to_json(output_path.with_suffix('.json'), orient='records', force_ascii=False, indent=2)
        
        if verbose:
            print(f"\nРасписание сохранено: {output_path.absolute()}")
        
        return str(output_path.absolute())

    def print_waiter_statistics(self, schedule_df: pd.DataFrame, min_hours: int):
        print("ПОДРОБНАЯ СТАТИСТИКА ПО ОФИЦИАНТАМ")
        
        # Группируем по официантам
        waiter_groups = schedule_df.groupby('waiter_num')
        
        for waiter_num, group in waiter_groups:
            waiter_id = group['waiter_id'].iloc[0]
            waiter_type = group['waiter_type'].iloc[0]
            capacity = group['waiter_capacity'].iloc[0]
            
            # Общая статистика
            total_shifts = (group['shift_type_code'] > 0).sum()
            total_hours = group['work_hours'].sum()
            days_worked = total_shifts
            days_off = len(group) - total_shifts
            
            # Статус выполнения нормы
            status = '1' if total_hours >= min_hours else '0'
            percent_of_min = (total_hours / min_hours * 100) if min_hours > 0 else 0
            
            # Распределение по типам смен
            full_shifts = (group['shift_type_code'] == 1).sum()
            morning_shifts = (group['shift_type_code'] == 2).sum()
            evening_shifts = (group['shift_type_code'] == 3).sum()
            
            # Распределение по дням недели
            group_copy = group.copy()
            group_copy['day_of_week'] = pd.to_datetime(group_copy['date']).dt.day_name()
            shifts_by_day = group_copy[group_copy['shift_type_code'] > 0].groupby('day_of_week').size()
            
            # Вывод информации по официанту
            print(f"\n{'─' * 70}")
            print(f"{waiter_id} | {waiter_type} ({capacity} гостей/час) {status}")
            print(f"{'─' * 70}")
            
            print(f"Общая статистика:")
            print(f"   Всего дней в периоде: {len(group)}")
            print(f"   Рабочих дней: {days_worked}")
            print(f"   Выходных: {days_off}")
            print(f"   Всего часов: {total_hours}")
            print(f"   Норма ({min_hours}ч): {percent_of_min:.1f}% {status}")
            
            print(f"\nТипы смен:")
            print(f"   Полные (13ч):   {full_shifts:>3} смен  ({full_shifts * 13:>3} ч)")
            print(f"   Утренние (6ч):  {morning_shifts:>3} смен  ({morning_shifts * 6:>3} ч)")
            print(f"   Вечерние (7ч):  {evening_shifts:>3} смен  ({evening_shifts * 7:>3} ч)")
            
            print(f"\nПо дням недели:")
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_names_ru = {'Monday': 'Пн', 'Tuesday': 'Вт', 'Wednesday': 'Ср', 
                           'Thursday': 'Чт', 'Friday': 'Пт', 'Saturday': 'Сб', 'Sunday': 'Вс'}
            
            for day_en in day_order:
                count = shifts_by_day.get(day_en, 0)
                bar = '-' * count
                print(f"   {day_names_ru[day_en]:<4}: {count:>2} смен  {bar}")
            
            # Календарь смен (первые 14 дней для компактности)
            print(f"\nКалендарь смен (первые 14 дней):")
            print(f"   {'Дата':<12} {'День':<4} {'Смена':<10} {'Часы':<6} {'Время':<12}")
            print(f"   {'─' * 46}")
            
            for _, row in group.head(14).iterrows():
                date_str = pd.to_datetime(row['date']).strftime('%Y-%m-%d')
                day_name = pd.to_datetime(row['date']).strftime('%a')
                shift = row['shift_type']
                hours = row['work_hours']
                
                if row['shift_type_code'] > 0:
                    start = int(row['work_start'])
                    end = int(row['work_end'])
                    
                    # Обработка перехода через полночь
                    if end > 24:
                        end_display = end - 24
                        time_str = f"{start}:00-{end_display}:00+1"
                    else:
                        time_str = f"{start}:00-{end}:00"
                else:
                    time_str = '—'
                
                print(f"   {date_str:<12} {day_name:<4} {shift:<10} {hours:>2} ч    {time_str:<12}")
            
            if len(group) > 14:
                print(f"   ... и ещё {len(group) - 14} дней")
        
        # Итоговая сводка
        print("ИТОГО ПО ВСЕМ ОФИЦИАНТАМ")
        
        total_hours_all = schedule_df[schedule_df['shift_type_code'] > 0]['work_hours'].sum()
        total_shifts_all = (schedule_df['shift_type_code'] > 0).sum()
        avg_hours = total_hours_all / len(waiter_groups)
        min_hours_actual = schedule_df.groupby('waiter_num')['work_hours'].sum().min()
        max_hours_actual = schedule_df.groupby('waiter_num')['work_hours'].sum().max()
        
        print(f"Всего часов работы: {total_hours_all}")
        print(f"Всего смен: {total_shifts_all}")
        print(f"Среднее часов на официанта: {avg_hours:.1f}")
        print(f"Минимум часов (официант): {min_hours_actual}")
        print(f"Максимум часов (официант): {max_hours_actual}")
        print(f"Разброс: {max_hours_actual - min_hours_actual} ч")
        
        # Проверка выполнения нормы всеми
        all_met = schedule_df.groupby('waiter_num')['work_hours'].sum().min() >= min_hours
        print(f"\nНорма {min_hours}ч выполнена всеми: {'Да' if all_met else 'Нет'}")

def create_waiter_schedule(
    forecast_path: str = None,
    waiter_config: Dict[int, str] = None,
    output_path: str = None,
    verbose: bool = True
) -> Tuple[pd.DataFrame, Dict]:
    if forecast_path is None:
        forecast_path = 'data/predicted/forecast.csv'
    
    if not Path(forecast_path).exists():
        raise FileNotFoundError(f"Файл прогноза не найден: {forecast_path}")
    
    # Конфигурация официантов по умолчанию: все новички
    if waiter_config is None:
        waiter_config = {i: 'novice' for i in range(1, 11)}  # 10 новичков
    
    if verbose:
        print(f"Загрузка прогноза из: {forecast_path}")
        print(f"Конфигурация официантов: {waiter_config}")
    
    forecast_df = pd.read_csv(forecast_path, encoding='utf-8-sig')
    forecast_df['datetime'] = pd.to_datetime(forecast_df['forecast_datetime'])
    
    scheduler = WaiterScheduler()
    
    schedule_df, stats = scheduler.create_schedule(
        forecast_df=forecast_df,
        waiter_config=waiter_config,
        verbose=verbose
    )
    
    if schedule_df is None:
        return None, {}
    
    if output_path is None:
        output_path = 'data/predicted/waiter_schedule.csv'
    
    scheduler.export_schedule(schedule_df, output_path, verbose=verbose)
    
    if verbose:
        # Рассчитываем минимальные часы пропорционально периоду
        num_days = len(schedule_df['date'].unique())
        min_hours = int(MIN_HOURS_PER_MONTH * num_days / 30)
        
        print(f"\nПериод: {num_days} дней")
        print(f"Минимальная норма часов: {min_hours} (из расчёта {MIN_HOURS_PER_MONTH}ч/месяц)")
        
        scheduler.print_schedule_summary(schedule_df, min_hours=min_hours)
    
    return schedule_df, stats


if __name__ == '__main__':
    waiter_config = {
        1: 'specialist',
        2: 'specialist',
        3: 'specialist',
        4: 'novice',
        5: 'novice'
    }
    
    schedule_df, stats = create_waiter_schedule(
        forecast_path='data/predicted/forecast.csv',
        waiter_config=waiter_config,
        output_path='data/predicted/waiter_schedule.csv',
        verbose=True
    )