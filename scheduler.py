import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
from pathlib import Path
from typing import Tuple, Dict, List, Optional
from src.config import MIN_WAITERS_ABSOLUTE


# КОНФИГУРАЦИЯ

WAITER_TYPES = {
    'specialist': {
        'name': 'Специалист',
        'capacity': 10,
        'code': 1
    },
    'novice': {
        'name': 'Новичок',
        'capacity': 5,
        'code': 2
    }
}

SHIFT_TYPES = {
    'full': {
        'name': 'Полная',
        'start': 10,
        'end': 22,
        'hours': 12,
        'code': 1,
        'covers_hours': list(range(10, 22))
    },
    'morning': {
        'name': 'Утренняя',
        'start': 10,
        'end': 16,
        'hours': 6,
        'code': 2,
        'covers_hours': list(range(10, 16))
    },
    'evening': {
        'name': 'Вечерняя',
        'start': 16,
        'end': 25,
        'hours': 9,
        'code': 3,
        'covers_hours': list(range(16, 23))
    },
    'off': {
        'name': 'Выходной',
        'start': None,
        'end': None,
        'hours': 0,
        'code': 0,
        'covers_hours': []
    }
}

MIN_HOURS_PER_MONTH = 200
AVG_CAPACITY = 7.5


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

def estimate_max_waiters(forecast_df: pd.DataFrame, min_hours: int = 200) -> Tuple[int, int, bool]:
    peak_guests = forecast_df['guests_with_buffer'].max()
    min_by_peak = max(MIN_WAITERS_ABSOLUTE, int(np.ceil(peak_guests / 10)))
    
    total_guests = forecast_df['guests_with_buffer'].sum()
    total_waiter_hours = int(np.ceil(total_guests / AVG_CAPACITY))
    
    min_waiters = MIN_WAITERS_ABSOLUTE
    max_by_hours = int(np.floor(total_waiter_hours / min_hours)) if min_hours > 0 else 10
    max_by_hours = max(max_by_hours, min_waiters)
    
    is_feasible = min_by_peak <= max_by_hours
    suggested_min_hours = max(10, int(total_waiter_hours / min_waiters * 0.95))
    
    if not is_feasible or min_hours > suggested_min_hours:
        print(f"Внимание: при {min_waiters} официантах и такой нагрузке:")
        print(f"   Доступно часов работы: {total_waiter_hours}")
        print(f"   Макс. норма на официанта: {suggested_min_hours}ч (вместо {min_hours}ч)")
    
    max_waiters = max(min_by_peak, max_by_hours) + 2
    return max_waiters, suggested_min_hours, is_feasible


def get_shift_for_hour(shift_code: int, hour: int) -> bool:
    if shift_code == 1:
        return 10 <= hour < 22
    elif shift_code == 2:
        return 10 <= hour < 16
    elif shift_code == 3:
        return 16 <= hour < 23
    return False


# ОСНОВНОЙ КЛАСС

class WaiterScheduler:
    def __init__(
        self,
        min_hours_per_waiter: int = MIN_HOURS_PER_MONTH,
        max_hours_per_week: int = 48,
        verbose: bool = True,
        best_effort: bool = True,
        novice_ratio: float = 0.5
    ):
        self.min_hours = min_hours_per_waiter
        self.max_weekly_hours = max_hours_per_week
        self.verbose = verbose
        self.best_effort = best_effort
        self.novice_ratio = novice_ratio
        self.work_start = 10
        self.work_end = 23
    
    def _prepare_data(self, forecast_df: pd.DataFrame) -> pd.DataFrame:
        df = forecast_df.copy()
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['date'] = df['datetime'].dt.date
        df['hour'] = df['datetime'].dt.hour
        
        guest_col = 'guests_with_buffer' if 'guests_with_buffer' in df.columns else 'guests_predicted'
        df['guests'] = df[guest_col].fillna(0).astype(int)
        
        return df
    
    def _create_model(
        self,
        df: pd.DataFrame,
        max_waiters: int,
        min_hours: int,
        best_effort: bool = None
    ) -> Tuple[cp_model.CpModel, cp_model.CpSolver, Dict]:
        
        if best_effort is None:
            best_effort = self.best_effort
        
        num_days = df['date'].nunique()
        date_list = sorted(df['date'].unique())
        date_to_idx = {d: i for i, d in enumerate(date_list)}
        
        model = cp_model.CpModel()
        
        # ПЕРЕМЕННЫЕ
        
        is_active = [model.NewBoolVar(f'active_{w}') for w in range(max_waiters)]
        model.Add(sum(is_active) >= MIN_WAITERS_ABSOLUTE)
        
        shift = {}
        for w in range(max_waiters):
            for d in range(num_days):
                for s in [1, 2, 3]:
                    var = model.NewBoolVar(f'shift_w{w}_d{d}_s{s}')
                    shift[(w, d, s)] = var
                    model.Add(var <= is_active[w])
        
        waiter_hours = {}
        for w in range(max_waiters):
            expr = sum(
                SHIFT_TYPES['full']['hours'] * shift[(w, d, 1)] +
                SHIFT_TYPES['morning']['hours'] * shift[(w, d, 2)] +
                SHIFT_TYPES['evening']['hours'] * shift[(w, d, 3)]
                for d in range(num_days)
            )
            waiter_hours[w] = model.NewIntVar(0, num_days * 13, f'hours_w{w}')
            model.Add(waiter_hours[w] == expr)
        
        waiter_shifts = {}
        for w in range(max_waiters):
            expr = sum(
                shift[(w, d, s)]
                for d in range(num_days)
                for s in [1, 2, 3]
            )
            waiter_shifts[w] = model.NewIntVar(0, num_days, f'shifts_w{w}')
            model.Add(waiter_shifts[w] == expr)
        
        # МЯГКИЕ ОГРАНИЧЕНИЯ
        
        for w in range(max_waiters):
            for start_day in range(num_days - 6):
                working = sum(
                    sum(shift[(w, d, s)] for s in [1, 2, 3])
                    for d in range(start_day, start_day + 7)
                )
                model.Add(working <= 6)
        
        for w in range(max_waiters):
            for start_day in range(num_days - 13):
                working = sum(
                    sum(shift[(w, d, s)] for s in [1, 2, 3])
                    for d in range(start_day, start_day + 14)
                )
                model.Add(working <= 12)
        
        # ОСНОВНЫЕ ОГРАНИЧЕНИЯ
        
        for w in range(max_waiters):
            for d in range(num_days):
                model.Add(sum(shift[(w, d, s)] for s in [1, 2, 3]) <= 1)
        
        for day in date_list:
            day_idx = date_to_idx[day]
            day_data = df[df['date'] == day]
            for hour in range(self.work_start, self.work_end):
                hour_data = day_data[day_data['hour'] == hour]
                if len(hour_data) == 0:
                    continue
                guests = hour_data['guests'].values[0]
                if guests <= 0:
                    continue
                needed = int(np.ceil(guests / 7.5))
                coverage = sum(
                    shift[(w, day_idx, s)]
                    for w in range(max_waiters)
                    for s in [1, 2, 3]
                    if get_shift_for_hour(s, hour)
                )
                model.Add(coverage >= needed)
        
        if best_effort:
            for w in range(max_waiters):
                model.Add(waiter_hours[w] >= 0)
                model.Add(waiter_hours[w] <= num_days * 13 * is_active[w])
        else:
            for w in range(max_waiters):
                model.Add(waiter_hours[w] >= min_hours * is_active[w])
                model.Add(waiter_hours[w] <= num_days * 13 * is_active[w])
        
        for w in range(max_waiters):
            for start_day in range(num_days - 6):
                weekly = sum(
                    SHIFT_TYPES['full']['hours'] * shift[(w, d, 1)] +
                    SHIFT_TYPES['morning']['hours'] * shift[(w, d, 2)] +
                    SHIFT_TYPES['evening']['hours'] * shift[(w, d, 3)]
                    for d in range(start_day, start_day + 7)
                )
                model.Add(weekly <= self.max_weekly_hours)
        
        for w1 in range(max_waiters):
            for w2 in range(w1 + 1, max_waiters):
                model.Add(waiter_shifts[w1] - waiter_shifts[w2] <= 5)
                model.Add(waiter_shifts[w2] - waiter_shifts[w1] <= 5)
        
        total_guests = df['guests'].sum()
        max_total_hours = int(np.ceil(total_guests / 3))
        model.Add(sum(waiter_hours[w] for w in range(max_waiters)) <= max_total_hours)
        
        # ЦЕЛЕВАЯ ФУНКЦИЯ
        
        if best_effort:
            target_hours = min_hours
            
            under_hours = []
            for w in range(max_waiters):
                dev = model.NewIntVar(0, target_hours, f'under_w{w}')
                model.Add(dev >= target_hours - waiter_hours[w])
                model.Add(dev >= 0)
                model.Add(dev <= target_hours * is_active[w])
                under_hours.append(dev)
            
            shift_imbalance = []
            for w1 in range(max_waiters):
                for w2 in range(w1 + 1, max_waiters):
                    diff = model.NewIntVar(0, num_days, f'diff_w{w1}_w{w2}')
                    model.Add(diff >= waiter_shifts[w1] - waiter_shifts[w2])
                    model.Add(diff >= waiter_shifts[w2] - waiter_shifts[w1])
                    shift_imbalance.append(diff)
            
            model.Minimize(
                sum(is_active) * 10 +
                sum(under_hours) * 0.01 +
                sum(shift_imbalance) * 0.1
            )
        else:
            model.Minimize(sum(is_active))
        
        # СОЛВЕР
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.num_search_workers = 8
        solver.parameters.cp_model_presolve = True
        solver.parameters.linearization_level = 1
        
        return model, solver, {
            'is_active': is_active,
            'shift': shift,
            'waiter_hours': waiter_hours,
            'waiter_shifts': waiter_shifts,
            'date_list': date_list,
            'num_days': num_days,
            'max_waiters': max_waiters,
            'target_hours': min_hours if best_effort else None
        }
    
    def _create_model_relaxed(
        self,
        df: pd.DataFrame,
        max_waiters: int,
        min_hours: int,
        best_effort: bool = None
    ) -> Tuple[cp_model.CpModel, cp_model.CpSolver, Dict]:
        
        if best_effort is None:
            best_effort = self.best_effort
        
        num_days = df['date'].nunique()
        date_list = sorted(df['date'].unique())
        date_to_idx = {d: i for i, d in enumerate(date_list)}
        
        model = cp_model.CpModel()
        
        # ПЕРЕМЕННЫЕ
        
        is_active = [model.NewBoolVar(f'active_{w}') for w in range(max_waiters)]
        model.Add(sum(is_active) >= MIN_WAITERS_ABSOLUTE)
        
        shift = {}
        for w in range(max_waiters):
            for d in range(num_days):
                for s in [1, 2, 3]:
                    var = model.NewBoolVar(f'shift_w{w}_d{d}_s{s}')
                    shift[(w, d, s)] = var
                    model.Add(var <= is_active[w])
        
        waiter_hours = {}
        for w in range(max_waiters):
            expr = sum(
                SHIFT_TYPES['full']['hours'] * shift[(w, d, 1)] +
                SHIFT_TYPES['morning']['hours'] * shift[(w, d, 2)] +
                SHIFT_TYPES['evening']['hours'] * shift[(w, d, 3)]
                for d in range(num_days)
            )
            waiter_hours[w] = model.NewIntVar(0, num_days * 13, f'hours_w{w}')
            model.Add(waiter_hours[w] == expr)
        
        waiter_shifts = {}
        for w in range(max_waiters):
            expr = sum(
                shift[(w, d, s)]
                for d in range(num_days)
                for s in [1, 2, 3]
            )
            waiter_shifts[w] = model.NewIntVar(0, num_days, f'shifts_w{w}')
            model.Add(waiter_shifts[w] == expr)
        
        # СТРОГИЕ ПАТТЕРНЫ — МОДЕЛЬ ВЫБИРАЕТ ДЛЯ КАЖДОГО ОФИЦИАНТА
        
        ALLOWED_PATTERNS = [
            (4, 2),  # 0: 4 рабочих, 2 выходных
            (4, 3),  # 1: 4 рабочих, 3 выходных
            (3, 2),  # 2: 3 рабочих, 2 выходных
            (2, 2),  # 3: 2 рабочих, 2 выходных
        ]
        
        waiter_pattern_var = {}
        
        for w in range(max_waiters):
            for start_day in range(num_days - 6):
                # Сумма смен за 7 дней подряд
                week_work = sum(
                    sum(shift[(w, d, s)] for s in [1, 2, 3])
                    for d in range(start_day, start_day + 7)
                )
                # Не более 6 рабочих дней в любой 7-дневный период
                model.Add(week_work <= 6)
        
        for w in range(max_waiters):
            # Модель выбирает ОДИН паттерн для этого официанта
            pattern_idx = model.NewIntVar(0, len(ALLOWED_PATTERNS) - 1, f'pattern_w{w}')
            waiter_pattern_var[w] = pattern_idx
            
            # Применяем выбранный паттерн на ВСЁМ периоде
            for p_idx, (work_days, rest_days) in enumerate(ALLOWED_PATTERNS):
                cycle = work_days + rest_days
                
                # Булева переменная: официант w использует паттерн p_idx
                uses_pattern = model.NewBoolVar(f'w{w}_p{p_idx}')
                model.Add(pattern_idx == p_idx).OnlyEnforceIf(uses_pattern)
                
                # Циклически применяем на все дни периода
                for cycle_start in range(0, num_days, cycle):
                    for day_in_cycle in range(cycle):
                        day = cycle_start + day_in_cycle
                        if day >= num_days:
                            continue
                        
                        is_work_day = day_in_cycle < work_days
                        
                        if is_work_day:
                            # В рабочий день: хотя бы одна смена
                            model.Add(sum(shift[(w, day, s)] for s in [1, 2, 3]) >= 1).OnlyEnforceIf(uses_pattern)
                        else:
                            # В выходной: никаких смен
                            for s in [1, 2, 3]:
                                model.Add(shift[(w, day, s)] == 0).OnlyEnforceIf(uses_pattern)
        
        # ОСНОВНЫЕ ОГРАНИЧЕНИЯ
        
        for w in range(max_waiters):
            for d in range(num_days):
                model.Add(sum(shift[(w, d, s)] for s in [1, 2, 3]) <= 1)
        
        for day in date_list:
            day_idx = date_to_idx[day]
            day_data = df[df['date'] == day]
            for hour in range(self.work_start, self.work_end):
                hour_data = day_data[day_data['hour'] == hour]
                if len(hour_data) == 0:
                    continue
                guests = hour_data['guests'].values[0]
                if guests <= 0:
                    continue
                needed = int(np.ceil(guests / 7.5))
                coverage = sum(
                    shift[(w, day_idx, s)]
                    for w in range(max_waiters)
                    for s in [1, 2, 3]
                    if get_shift_for_hour(s, hour)
                )
                model.Add(coverage >= needed)
        
        if best_effort:
            for w in range(max_waiters):
                model.Add(waiter_hours[w] >= 0)
        else:
            for w in range(max_waiters):
                model.Add(waiter_hours[w] >= min_hours * is_active[w])
        
        # БАЛАНСИРОВКА
        
        max_imbalance = 5
        
        for w1 in range(max_waiters):
            for w2 in range(w1 + 1, max_waiters):
                model.Add(waiter_shifts[w1] - waiter_shifts[w2] <= max_imbalance)
                model.Add(waiter_shifts[w2] - waiter_shifts[w1] <= max_imbalance)
        
        total_guests = df['guests'].sum()
        max_total_hours = int(np.ceil(total_guests / 3))
        model.Add(sum(waiter_hours[w] for w in range(max_waiters)) <= max_total_hours)
        
        # ЦЕЛЕВАЯ ФУНКЦИЯ
        
        if best_effort:
            objective = sum(is_active) * 100
            
            shift_imbalance = []
            for w1 in range(max_waiters):
                for w2 in range(w1 + 1, max_waiters):
                    diff = model.NewIntVar(0, num_days, f'diff_w{w1}_w{w2}')
                    model.Add(diff >= waiter_shifts[w1] - waiter_shifts[w2])
                    model.Add(diff >= waiter_shifts[w2] - waiter_shifts[w1])
                    shift_imbalance.append(diff)
            
            objective += sum(shift_imbalance) * 10
            
            model.Minimize(objective)
        else:
            model.Minimize(sum(is_active))
        
        # СОЛВЕР
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300.0
        solver.parameters.num_search_workers = 8
        solver.parameters.cp_model_presolve = True
        solver.parameters.linearization_level = 1
        
        return model, solver, {
            'is_active': is_active,
            'shift': shift,
            'waiter_hours': waiter_hours,
            'waiter_shifts': waiter_shifts,
            'date_list': date_list,
            'num_days': num_days,
            'max_waiters': max_waiters,
            'target_hours': min_hours if best_effort else None,
            'waiter_pattern_var': waiter_pattern_var,
            'allowed_patterns': ALLOWED_PATTERNS
        }
    
    def _extract_solution(
        self,
        solver: cp_model.CpSolver,
        vars_dict: Dict,
        df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict]:
        
        is_active = vars_dict['is_active']
        shift = vars_dict['shift']
        date_list = vars_dict['date_list']
        num_days = vars_dict['num_days']
        max_waiters = vars_dict['max_waiters']
        
        active_waiters = [w for w in range(max_waiters) if solver.Value(is_active[w]) == 1]
        num_active = len(active_waiters)
        
        num_novices = int(np.ceil(num_active * self.novice_ratio))
        num_specialists = num_active - num_novices
        
        if self.verbose:
            print(f"Активные официанты: {len(active_waiters)}")
        
        schedule_data = []
        
        SHIFT_INFO = {
            1: {'name': 'Полная', 'start': 10, 'end': 22, 'hours': 12},
            2: {'name': 'Утренняя', 'start': 10, 'end': 16, 'hours': 6},
            3: {'name': 'Вечерняя', 'start': 16, 'end': 25, 'hours': 9},
        }
        
        for w in active_waiters:
            waiter_type = 'novice' if w >= num_specialists else 'specialist'
            
            for d in range(num_days):
                shift_code = 0
                shift_name = 'Выходной'
                work_start = work_end = None
                work_hours = 0
                
                for s in [1, 2, 3]:
                    if solver.Value(shift[(w, d, s)]) == 1:
                        shift_code = s
                        shift_name = SHIFT_INFO[s]['name']
                        work_start = SHIFT_INFO[s]['start']
                        work_end = SHIFT_INFO[s]['end']
                        work_hours = SHIFT_INFO[s]['hours']
                        break
                
                day_data = df[df['date'] == date_list[d]]
                day_guests = day_data['guests'].max() if len(day_data) > 0 else 0
                
                schedule_data.append({
                    'date': date_list[d],
                    'waiter_id': f'Официант {w+1}',
                    'waiter_num': w+1,
                    'waiter_type': WAITER_TYPES[waiter_type]['name'],
                    'waiter_type_code': WAITER_TYPES[waiter_type]['code'],
                    'waiter_capacity': WAITER_TYPES[waiter_type]['capacity'],
                    'shift_type_code': shift_code,
                    'shift_type': shift_name,
                    'work_start': work_start,
                    'work_end': work_end,
                    'work_hours': work_hours,
                    'guests_predicted': day_guests
                })
        
        schedule_df = pd.DataFrame(schedule_data)
        
        total_hours = schedule_df['work_hours'].sum()
        hours_per_waiter = schedule_df.groupby('waiter_num')['work_hours'].sum()
        
        shifts_per_waiter = schedule_df.groupby('waiter_num').apply(
            lambda x: pd.Series({
                'total_shifts': (x['shift_type_code'] > 0).sum(),
                'full_shifts': (x['shift_type_code'] == 1).sum(),
                'morning_shifts': (x['shift_type_code'] == 2).sum(),
                'evening_shifts': (x['shift_type_code'] == 3).sum(),
            })
        ).to_dict('index')
        
        # Извлекаем паттерны каждого официанта
        waiter_pattern_var = vars_dict.get('waiter_pattern_var', {})
        allowed_patterns = vars_dict.get('allowed_patterns', [(4, 2)])
        
        pattern_info = {}
        for w in active_waiters:
            if w in waiter_pattern_var:
                p_idx = solver.Value(waiter_pattern_var[w])
                work, rest = allowed_patterns[p_idx]
                pattern_info[w+1] = f"{work}/{rest}"
        
        stats = {
            'num_waiters': len(active_waiters),
            'num_specialists': num_specialists,
            'num_novices': num_novices,
            'novice_ratio': self.novice_ratio,
            'total_hours': int(total_hours),
            'total_shifts': int((schedule_df['shift_type_code'] > 0).sum()),
            'avg_hours_per_waiter': float(total_hours / len(active_waiters)) if active_waiters else 0,
            'min_hours': int(hours_per_waiter.min()) if len(hours_per_waiter) > 0 else 0,
            'max_hours': int(hours_per_waiter.max()) if len(hours_per_waiter) > 0 else 0,
            'all_met_min': bool((hours_per_waiter >= self.min_hours).all()),
            'full_shifts': int((schedule_df['shift_type_code'] == 1).sum()),
            'morning_shifts': int((schedule_df['shift_type_code'] == 2).sum()),
            'evening_shifts': int((schedule_df['shift_type_code'] == 3).sum()),
            'shifts_per_waiter': shifts_per_waiter,
            'hours_per_waiter': hours_per_waiter.to_dict(),
            'waiter_patterns': pattern_info 
        }
        
        waiter_pattern_var = vars_dict.get('waiter_pattern_var', {})
        allowed_patterns = vars_dict.get('allowed_patterns', [(4, 2)])
        
        pattern_info = {}
        for w in range(vars_dict['max_waiters']):
            if solver.Value(vars_dict['is_active'][w]) == 1:
                if w in waiter_pattern_var:
                    p_idx = solver.Value(waiter_pattern_var[w])
                    work, rest = allowed_patterns[p_idx]
                    pattern_info[w+1] = f"{work}/{rest}"
        
        stats['waiter_patterns'] = pattern_info
        
        return schedule_df, stats
    
    def _count_max_consecutive_shifts(self, group: pd.DataFrame) -> int:
        group = group.sort_values('date')
        working = (group['shift_type_code'] > 0).astype(int)
        
        max_consecutive = 0
        current = 0
        
        for val in working:
            if val == 1:
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 0
        
        return max_consecutive
    
    def print_waiter_summary(self, schedule_df: pd.DataFrame, stats: Dict):
        
        if schedule_df.empty:
            print("Расписание пустое")
            return
        
        print("СВОДКА ПО ОФИЦИАНТАМ")
        
        if stats.get('is_long_period'):
            print(f"\nДлинный период: ограничения ослаблены для поиска решения")
            print(f"   • Макс. рабочих дней подряд: 7 (вместо 6)")
            print(f"   • Баланс смен: разброс ≤10 (вместо ≤5)")
        
        print(f"\n{'Официант':<12} {'Тип':<12} {'Смен':<8} {'Полн':<6} {'Утр':<5} {'Веч':<5} {'Часов':<8} {'Ср. ч/смену':<12}")
        print("-" * 70)
        
        for waiter_num, group in schedule_df.groupby('waiter_num'):
            waiter_id = group['waiter_id'].iloc[0]
            waiter_type = group['waiter_type'].iloc[0]
            
            total_shifts = (group['shift_type_code'] > 0).sum()
            full_shifts = (group['shift_type_code'] == 1).sum()
            morning_shifts = (group['shift_type_code'] == 2).sum()
            evening_shifts = (group['shift_type_code'] == 3).sum()
            total_hours = group['work_hours'].sum()
            avg_per_shift = total_hours / total_shifts if total_shifts > 0 else 0
            
            print(f"{waiter_id:<12} {waiter_type:<12} {total_shifts:<8} {full_shifts:<6} {morning_shifts:<5} {evening_shifts:<5} {total_hours:<8} {avg_per_shift:<12.1f}")
        
        print("-" * 70)
        
        shifts_list = [stats['shifts_per_waiter'][w]['total_shifts'] for w in stats['shifts_per_waiter']]
        if len(shifts_list) > 1:
            min_shifts = min(shifts_list)
            max_shifts = max(shifts_list)
            avg_shifts = sum(shifts_list) / len(shifts_list)
            imbalance = max_shifts - min_shifts
            
            print(f"\nБалансировка смен:")
            print(f"   Мин смен: {min_shifts}, Макс смен: {max_shifts}")
            print(f"   Среднее: {avg_shifts:.1f}, Разброс: {imbalance} смен")
            
            if imbalance <= 3:
                print(f"   Отличная балансировка (≤3)")
            elif imbalance <= 5:
                print(f"   Хорошая балансировка (≤5)")
            else:
                print(f"   Разбалансировка (>5)")
        
        total_shifts = (schedule_df['shift_type_code'] > 0).sum()
        total_hours = schedule_df['work_hours'].sum()
        print(f"\n{'ВСЕГО':<12} {'':<12} {total_shifts:<8} {stats.get('full_shifts', 0):<6} {stats.get('morning_shifts', 0):<5} {stats.get('evening_shifts', 0):<5} {total_hours:<8} {total_hours/total_shifts if total_shifts > 0 else 0:<12.1f}")
        
        print(f"\nРаспределение смен:")
        print(f"   Полные (12ч):   {stats.get('full_shifts', 0):>3} ({stats.get('full_shifts', 0)/total_shifts*100 if total_shifts > 0 else 0:.1f}%)")
        print(f"   Утренние (6ч):  {stats.get('morning_shifts', 0):>3} ({stats.get('morning_shifts', 0)/total_shifts*100 if total_shifts > 0 else 0:.1f}%)")
        print(f"   Вечерние (9ч):  {stats.get('evening_shifts', 0):>3} ({stats.get('evening_shifts', 0)/total_shifts*100 if total_shifts > 0 else 0:.1f}%)")
        
        print(f"\nПо типам официантов:")
        type_summary = schedule_df[schedule_df['shift_type_code'] > 0].groupby('waiter_type').agg({
            'work_hours': 'sum',
            'shift_type_code': 'count'
        })
        for waiter_type, row in type_summary.iterrows():
            print(f"   {waiter_type:<12}: {int(row['work_hours']):>4} ч, {int(row['shift_type_code']):>3} смен")
    
    def _create_model_with_strict_patterns(
        self,
        df: pd.DataFrame,
        max_waiters: int,
        min_hours: int,
        patterns: list
    ) -> Tuple[cp_model.CpModel, cp_model.CpSolver, Dict]: 
        num_days = df['date'].nunique()
        date_list = sorted(df['date'].unique())
        date_to_idx = {d: i for i, d in enumerate(date_list)}
        
        model = cp_model.CpModel()
        
        # ПЕРЕМЕННЫЕ
        
        is_active = [model.NewBoolVar(f'active_{w}') for w in range(max_waiters)]
        model.Add(sum(is_active) >= MIN_WAITERS_ABSOLUTE)
        
        shift = {}
        for w in range(max_waiters):
            for d in range(num_days):
                for s in [1, 2, 3]:
                    var = model.NewBoolVar(f'shift_w{w}_d{d}_s{s}')
                    shift[(w, d, s)] = var
                    model.Add(var <= is_active[w])
        
        waiter_hours = {}
        for w in range(max_waiters):
            expr = sum(
                SHIFT_TYPES['full']['hours'] * shift[(w, d, 1)] +
                SHIFT_TYPES['morning']['hours'] * shift[(w, d, 2)] +
                SHIFT_TYPES['evening']['hours'] * shift[(w, d, 3)]
                for d in range(num_days)
            )
            waiter_hours[w] = model.NewIntVar(0, num_days * 13, f'hours_w{w}')
            model.Add(waiter_hours[w] == expr)
        
        waiter_shifts = {}
        for w in range(max_waiters):
            expr = sum(
                shift[(w, d, s)]
                for d in range(num_days)
                for s in [1, 2, 3]
            )
            waiter_shifts[w] = model.NewIntVar(0, num_days, f'shifts_w{w}')
            model.Add(waiter_shifts[w] == expr)
        
        # ГИБКИЕ ПАТТЕРНЫ СО СДВИГОМ (ключевое улучшение)
        
        waiter_pattern_var = {}
        
        for w in range(max_waiters):
            pattern_bools = []
            
            for p_idx, (work_days, rest_days) in enumerate(patterns):
                cycle = work_days + rest_days
                
                # Переменная: сдвиг начала цикла (0..cycle-1)
                shift_var = model.NewIntVar(0, cycle - 1, f'shift_w{w}_p{p_idx}')
                
                for s in range(cycle):
                    # Булева: этот официант использует паттерн p_idx со сдвигом s
                    uses_pattern_shift = model.NewBoolVar(f'w{w}_p{p_idx}_s{s}')
                    
                    # Применяем паттерн со сдвигом
                    for day in range(num_days):
                        # Позиция в цикле со сдвигом
                        pos_in_cycle = (day - s) % cycle
                        is_work_day = pos_in_cycle < work_days
                        
                        if is_work_day:
                            model.Add(sum(shift[(w, day, s_type)] for s_type in [1, 2, 3]) >= 1).OnlyEnforceIf(uses_pattern_shift)
                        else:
                            for s_type in [1, 2, 3]:
                                model.Add(shift[(w, day, s_type)] == 0).OnlyEnforceIf(uses_pattern_shift)
                    
                    pattern_bools.append(uses_pattern_shift)
            
            # Ровно одна комбинация (паттерн + сдвиг) должна быть выбрана
            model.Add(sum(pattern_bools) == 1)
            
            # Сохраняем для извлечения
            waiter_pattern_var[w] = model.NewIntVar(0, len(patterns) * max(p[0]+p[1] for p in patterns) - 1, f'pattern_w{w}')
        
        # ОСНОВНЫЕ ОГРАНИЧЕНИЯ (покрытие, одна смена в день, и т.д.)
        
        for w in range(max_waiters):
            for d in range(num_days):
                model.Add(sum(shift[(w, d, s)] for s in [1, 2, 3]) <= 1)
        
        for day in date_list:
            day_idx = date_to_idx[day]
            day_data = df[df['date'] == day]
            for hour in range(self.work_start, self.work_end):
                hour_data = day_data[day_data['hour'] == hour]
                if len(hour_data) == 0:
                    continue
                guests = hour_data['guests'].values[0]
                if guests <= 0:
                    continue
                needed = int(np.ceil(guests / 7.5))
                coverage = sum(
                    shift[(w, day_idx, s)]
                    for w in range(max_waiters)
                    for s in [1, 2, 3]
                    if get_shift_for_hour(s, hour)
                )
                model.Add(coverage >= needed)
        
        if self.best_effort:
            for w in range(max_waiters):
                model.Add(waiter_hours[w] >= 0)
        else:
            for w in range(max_waiters):
                model.Add(waiter_hours[w] >= min_hours * is_active[w])
        
        # БАЛАНСИРОВКА
        
        max_imbalance = 5
        for w1 in range(max_waiters):
            for w2 in range(w1 + 1, max_waiters):
                model.Add(waiter_shifts[w1] - waiter_shifts[w2] <= max_imbalance)
                model.Add(waiter_shifts[w2] - waiter_shifts[w1] <= max_imbalance)
        
        total_guests = df['guests'].sum()
        max_total_hours = int(np.ceil(total_guests / 3))
        model.Add(sum(waiter_hours[w] for w in range(max_waiters)) <= max_total_hours)
        
        # ЦЕЛЕВАЯ ФУНКЦИЯ
        
        if self.best_effort:
            objective = sum(is_active) * 100
            
            shift_imbalance = []
            for w1 in range(max_waiters):
                for w2 in range(w1 + 1, max_waiters):
                    diff = model.NewIntVar(0, num_days, f'diff_w{w1}_w{w2}')
                    model.Add(diff >= waiter_shifts[w1] - waiter_shifts[w2])
                    model.Add(diff >= waiter_shifts[w2] - waiter_shifts[w1])
                    shift_imbalance.append(diff)
            
            objective += sum(shift_imbalance) * 10
            model.Minimize(objective)
        else:
            model.Minimize(sum(is_active))
        
        # СОЛВЕР
        
        solver = cp_model.CpSolver()
        
        return model, solver, {
            'is_active': is_active,
            'shift': shift,
            'waiter_hours': waiter_hours,
            'waiter_shifts': waiter_shifts,
            'date_list': date_list,
            'num_days': num_days,
            'max_waiters': max_waiters,
            'target_hours': min_hours if self.best_effort else None,
            'waiter_pattern_var': waiter_pattern_var,
            'allowed_patterns': patterns
        }
    
    def create_schedule(
        self,
        forecast_df: pd.DataFrame,
        verbose: Optional[bool] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        
        if verbose is not None:
            self.verbose = verbose
        
        if self.verbose:
            print("ПЛАНИРОВАНИЕ СМЕН ОФИЦИАНТОВ")
            if self.best_effort:
                print("Режим: best effort (максимально близко к норме)")
        
        df = self._prepare_data(forecast_df)
        num_days = df['date'].nunique()
        num_months = num_days / 30.0
        
        if self.verbose:
            print(f"Период: {num_days} дней (~{num_months:.1f} месяцев)")
            print(f"Пиковая нагрузка: {df['guests'].max()} гостей/час")
            print(f"Минимум официантов: {MIN_WAITERS_ABSOLUTE}")
        
        total_min_hours = int(self.min_hours * num_months)
        
        if self.verbose:
            print(f"Норма часов: {self.min_hours}ч/мес × {num_months:.1f}мес = {total_min_hours}ч")
        
        # ИТЕРАТИВНОЕ ПЛАНИРОВАНИЕ СО СТРОГИМИ ПАТТЕРНАМИ
        
        # Начальное количество официантов
        base_waiters = max(MIN_WAITERS_ABSOLUTE, int(np.ceil(df['guests'].max() / 10)))
        
        # Максимальное количество для итераций
        max_waiters_limit = 15  # Не больше 15 официантов
        
        # Строгие паттерны
        STRICT_PATTERNS = [
            (4, 3),  # 4/3
            (4, 2),  # 4/2
            (3, 2),  # 3/2
            (2, 2),  # 2/2
        ]
        
        schedule_df = pd.DataFrame()
        stats = {}
        final_waiters = 0
        
        if self.verbose:
            print(f"\nИтеративное планирование со строгими паттернами:")
            print(f"   Паттерны: 4/3, 4/2, 3/2, 2/2")
            print(f"   Старт: {base_waiters} официантов")
            print(f"   Макс: {max_waiters_limit} официантов")
        
        # Цикл попыток с увеличением штата
        for num_waiters in range(base_waiters, max_waiters_limit + 1):
            if self.verbose:
                print(f"\nПопытка {num_waiters - base_waiters + 1}: {num_waiters} официантов...")
            
            # Оценка нормы часов для текущего количества
            total_guests = df['guests'].sum()
            total_waiter_hours = int(np.ceil(total_guests / AVG_CAPACITY))
            suggested_min_hours = max(10, int(total_waiter_hours / num_waiters * 0.95))
            actual_min_hours = min(total_min_hours, suggested_min_hours)
            
            if self.verbose and num_waiters > base_waiters:
                print(f"   Адаптация нормы: {total_min_hours}ч → {actual_min_hours}ч")
            
            # Создаём модель со строгими паттернами
            model, solver, vars_dict = self._create_model_with_strict_patterns(
                df, num_waiters, actual_min_hours, STRICT_PATTERNS
            )
            
            # Таймаут увеличивается с каждой попыткой
            timeout = 60.0 + (num_waiters - base_waiters) * 30.0
            solver.parameters.max_time_in_seconds = timeout
            solver.parameters.num_search_workers = 8
            solver.parameters.cp_model_presolve = True
            solver.parameters.linearization_level = 1
            
            status = solver.Solve(model)
            
            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                if self.verbose:
                    print(f"   OPTIMAL: найдено решение с {num_waiters} официантами!")
                
                schedule_df, stats = self._extract_solution(solver, vars_dict, df)
                final_waiters = num_waiters
                break
            else:
                if self.verbose:
                    print(f"   INFEASIBLE — пробуем с {num_waiters + 1} официантами...")
        
        # ОБРАБОТКА РЕЗУЛЬТАТА
        
        if schedule_df.empty:
            if self.verbose:
                print(f"\nНе удалось создать расписание даже с {max_waiters_limit} официантами")
                print("Попробуйте:")
                print("   • Увеличить max_waiters_limit в коде")
                print("   • Уменьшить норму часов")
                print("   • Проверить данные прогноза")
            return pd.DataFrame(), {}
        
        # Обновляем статистику
        stats['num_waiters'] = final_waiters
        stats['best_effort'] = self.best_effort
        stats['num_months'] = num_months
        stats['min_hours_per_month'] = self.min_hours
        stats['total_min_hours'] = total_min_hours
        stats['strict_patterns'] = True
        
        if self.verbose:
            print("РЕЗУЛЬТАТЫ:")
            print(f"   Официантов: {stats['num_waiters']} (минимум {MIN_WAITERS_ABSOLUTE})")
            print(f"   Всего часов: {stats['total_hours']}")
            print(f"   Часов/официант: {stats['avg_hours_per_waiter']:.1f}")
            
            self.print_waiter_summary(schedule_df, stats)
            
            if self.best_effort:
                target = actual_min_hours
                print(f"\nПериод: {num_months:.1f} месяцев")
                print(f"Цель: {target}ч ({self.min_hours}ч/мес × {num_months:.1f}мес)")
                print(f"   Фактически: {stats['avg_hours_per_waiter']:.1f}ч")
                if stats['avg_hours_per_waiter'] >= target * 0.8:
                    print(f"   Достигнуто ≥80% цели")
                else:
                    print(f"   Достигнуто {stats['avg_hours_per_waiter']/target*100:.0f}% цели")
        
        return schedule_df, stats


# ВНЕШНИЙ ИНТЕРФЕЙС

def create_waiter_schedule(
    forecast_path: str,
    output_path: Optional[str] = None,
    min_hours_per_waiter: int = MIN_HOURS_PER_MONTH,
    best_effort: bool = True,
    novice_ratio: float = 0.5,
    verbose: bool = True
) -> Tuple[pd.DataFrame, Dict]:
    
    if verbose:
        print(f"Загрузка прогноза: {forecast_path}")
    
    forecast_df = pd.read_csv(forecast_path, parse_dates=['datetime'])
    
    scheduler = WaiterScheduler(
        min_hours_per_waiter=min_hours_per_waiter,
        best_effort=best_effort,
        novice_ratio=novice_ratio,
        verbose=verbose
    )
    
    schedule_df, stats = scheduler.create_schedule(
        forecast_df=forecast_df,
        verbose=verbose
    )
    
    if output_path and not schedule_df.empty:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        schedule_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        if verbose:
            print(f"\nРасписание сохранено: {output_path}")
    
    return schedule_df, stats