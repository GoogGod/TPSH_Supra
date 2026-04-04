import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# КОНФИГУРАЦИЯ 

PATTERNS = {
    '4_3': {'work': 4, 'rest': 3, 'cycle': 7},
    '4_2': {'work': 4, 'rest': 2, 'cycle': 6},
    '3_2': {'work': 3, 'rest': 2, 'cycle': 5},
}

SHIFT_TYPES = {
    'full': {'name': 'Полная', 'hours': 12, 'code': 1},
    'morning': {'name': 'Утренняя', 'hours': 6, 'code': 2},
    'evening': {'name': 'Вечерняя', 'hours': 9, 'code': 3},
}

MIN_WAITERS = 5
NOVICE_RATIO = 0.3
TARGET_HOURS_PER_MONTH = 200
MIN_COVERAGE_RATIO = 1.0  # Минимальное покрытие (1.0 = 100%)
MAX_CONSECUTIVE_DAYS = 6  # Максимум рабочих дней подряд


# ПРОВЕРКИ (МИНИМАЛЬНЫЙ НАБОР)

def check_max_consecutive_days(schedule_df, max_consecutive=MAX_CONSECUTIVE_DAYS, verbose=False):
    schedule_df = schedule_df.copy()
    schedule_df['date'] = pd.to_datetime(schedule_df['date'])
    schedule_df = schedule_df.sort_values(['waiter_num', 'date'])
    
    violations = []
    
    for waiter_num in schedule_df['waiter_num'].unique():
        waiter_data = schedule_df[schedule_df['waiter_num'] == waiter_num].copy()
        waiter_data = waiter_data.sort_values('date')
        
        consecutive = 0
        max_consecutive_for_waiter = 0
        
        for idx, row in waiter_data.iterrows():
            if row['shift_type_code'] > 0:
                consecutive += 1
                if consecutive > max_consecutive_for_waiter:
                    max_consecutive_for_waiter = consecutive
            else:
                consecutive = 0
        
        if max_consecutive_for_waiter > max_consecutive:
            violations.append({
                'waiter_num': waiter_num,
                'max_consecutive': max_consecutive_for_waiter
            })
    
    if verbose and len(violations) > 0:
        print(f"\nНайдено {len(violations)} нарушений (>{max_consecutive} дней подряд):")
        for v in violations:
            print(f"   Официант {v['waiter_num']}: {v['max_consecutive']} дней подряд")
    
    return len(violations) == 0, violations


def reduce_overtime(schedule_df, forecast_df, target_hours=200, max_overtime_pct=0.15, verbose=True):
    df = forecast_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['month'] = df['datetime'].dt.to_period('M')
    
    schedule_df = schedule_df.copy()
    schedule_df['date'] = pd.to_datetime(schedule_df['date']).dt.date
    schedule_df['month'] = pd.to_datetime(schedule_df['date']).dt.to_period('M')
    
    days_per_month = schedule_df.groupby('month')['date'].nunique()
    complete_months = days_per_month[days_per_month >= 25].index.tolist()
    
    if len(complete_months) == 0:
        return schedule_df
    
    if verbose:
        print("СНИЖЕНИЕ ЧРЕЗМЕРНОЙ ПЕРЕРАБОТКИ")
    
    total_reductions = 0
    
    for waiter_num in schedule_df['waiter_num'].unique():
        waiter_data = schedule_df[schedule_df['waiter_num'] == waiter_num]
        
        for month in complete_months:
            if month not in waiter_data['month'].values:
                continue
                
            month_mask = waiter_data['month'] == month
            current_hours = waiter_data[month_mask]['work_hours'].sum()
            
            max_allowed = target_hours * (1 + max_overtime_pct)
            excess = current_hours - max_allowed
            
            if excess <= 0:
                continue
            
            month_data = waiter_data[month_mask].copy()
            full_shifts = month_data[month_data['shift_type_code'] == 1].copy()
            
            if len(full_shifts) == 0:
                continue
            
            full_shifts['day_guests'] = full_shifts['date'].apply(
                lambda d: df[df['date'] == d]['guests'].max() if len(df[df['date'] == d]) > 0 else 0
            )
            full_shifts = full_shifts.sort_values('day_guests', ascending=True)
            
            for idx, row in full_shifts.iterrows():
                if excess <= 0:
                    break
                
                if row.get('is_pattern_work_day', True) == False:
                    continue
                
                hours_reduced = 3
                mask = (schedule_df['waiter_num'] == waiter_num) & (schedule_df['date'] == row['date'])
                schedule_df.loc[mask, 'shift_type_code'] = 3
                schedule_df.loc[mask, 'shift_type'] = 'Вечерняя'
                schedule_df.loc[mask, 'work_hours'] = 9
                schedule_df.loc[mask, 'work_start'] = 16
                schedule_df.loc[mask, 'work_end'] = 25
                
                excess -= hours_reduced
                total_reductions += 1
                
                if verbose and total_reductions <= 5:
                    print(f"      {row['date']}: Полная (12ч) -> Вечерняя (9ч) [-3ч]")
    
    if verbose:
        if total_reductions > 0:
            print(f"\n   Всего смен снижено: {total_reductions}")
    
    return schedule_df


def check_hourly_coverage(schedule_df, forecast_df, verbose=True):
    df = forecast_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['hour'] = df['datetime'].dt.hour
    
    guest_col = 'guests_with_buffer' if 'guests_with_buffer' in df.columns else 'guests_predicted'
    df['guests'] = df[guest_col].fillna(0).astype(int)
    
    merged = schedule_df.merge(df[['date', 'hour', 'guests']].drop_duplicates(), on=['date'])
    
    hourly = merged.groupby(['date', 'hour']).agg({
        'waiter_capacity': 'sum',
        'guests': 'sum',
        'waiter_id': 'count'
    }).reset_index()
    
    hourly['needed'] = np.ceil(hourly['guests'] / 7.5)
    hourly['coverage_ratio'] = hourly['waiter_capacity'] / hourly['needed'].replace(0, 1)
    hourly['has_coverage'] = hourly['coverage_ratio'] >= MIN_COVERAGE_RATIO
    
    gaps = hourly[hourly['has_coverage'] == False]
    
    if verbose:
        coverage_rate = hourly['has_coverage'].mean() * 100
        print(f"\nПроверка почасового покрытия:")
        print(f"   Всего часов: {len(hourly)}")
        print(f"   Покрытие >=100%: {coverage_rate:.1f}%")
        
        if len(gaps) > 0:
            print(f"    Найдено {len(gaps)} часов с недостаточным покрытием!")
    
    return len(gaps) == 0, gaps


def get_shift_type_by_hourly_demand(day_data, verbose=False, morning_ratio=0.15):
    if len(day_data) == 0:
        return 'morning'
    
    peak_hour_guests = day_data.groupby('hour')['guests'].max().max()
    avg_guests = day_data['guests'].mean()
    
    if np.random.random() < morning_ratio and avg_guests < 10:
        return 'morning'
    
    if peak_hour_guests > 20 or avg_guests > 12:
        return 'full'
    elif peak_hour_guests > 12 or avg_guests > 7:
        return 'evening'
    else:
        return 'morning'


def ensure_min_waiters_per_day(schedule_df, forecast_df, min_per_day=5, verbose=True):
    daily_count = schedule_df.groupby('date').apply(
        lambda x: (x['shift_type_code'] > 0).sum()
    )
    
    days_with_gaps = daily_count[daily_count < min_per_day]
    
    if verbose and len(days_with_gaps) > 0:
        print(f"\nНайдено {len(days_with_gaps)} дней с <{min_per_day} официантами")
    
    return len(days_with_gaps) == 0, days_with_gaps


def balance_hours(schedule_df, target_hours=200, tolerance=0.2, verbose=True):
    hours_per_waiter = schedule_df.groupby('waiter_num')['work_hours'].sum()
    
    avg_hours = hours_per_waiter.mean()
    min_hours = hours_per_waiter.min()
    max_hours = hours_per_waiter.max()
    
    over = hours_per_waiter[hours_per_waiter > target_hours * (1 + tolerance)]
    under = hours_per_waiter[hours_per_waiter < target_hours * (1 - tolerance)]
    
    if verbose:
        print(f"\nБалансировка часов: Среднее={avg_hours:.1f}ч, Мин={min_hours:.1f}ч, Макс={max_hours:.1f}ч")
    
    is_balanced = len(over) == 0 and len(under) == 0
    return is_balanced, {'over': over, 'under': under, 'avg': avg_hours}


def add_extra_shifts(schedule_df, forecast_df, gaps_df, verbose=True):
    if len(gaps_df) == 0:
        return schedule_df, 0
    
    schedule_df = schedule_df.copy()
    extra_shifts_added = 0
    
    for _, gap in gaps_df.iterrows():
        gap_date = gap['date']
        off_duty = schedule_df[
            (schedule_df['date'] == gap_date) & 
            (schedule_df['shift_type_code'] == 0)
        ]['waiter_num'].unique()
        
        if len(off_duty) > 0:
            waiter_num = off_duty[0]
            mask = (schedule_df['date'] == gap_date) & (schedule_df['waiter_num'] == waiter_num)
            schedule_df.loc[mask, 'shift_type_code'] = 3
            schedule_df.loc[mask, 'shift_type'] = 'Вечерняя'
            schedule_df.loc[mask, 'work_hours'] = 9
            
            extra_shifts_added += 1
    
    return schedule_df, extra_shifts_added


def upgrade_shifts_to_full(schedule_df, forecast_df, target_hours_per_month=200, verbose=True):
    df = forecast_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['month'] = df['datetime'].dt.to_period('M')
    
    schedule_df = schedule_df.copy()
    schedule_df['date'] = pd.to_datetime(schedule_df['date']).dt.date
    schedule_df['month'] = pd.to_datetime(schedule_df['date']).dt.to_period('M')
    
    days_per_month = schedule_df.groupby('month')['date'].nunique()
    complete_months = days_per_month[days_per_month >= 25].index.tolist()
    
    if len(complete_months) == 0:
        complete_months = schedule_df['month'].unique().tolist()
    
    hours_by_waiter_month = schedule_df.groupby(['waiter_num', 'month'])['work_hours'].sum().unstack(fill_value=0)
    
    if verbose:
        print("УВЕЛИЧЕНИЕ ЧАСОВ ЧЕРЕЗ ЗАМЕНУ СМЕН НА ПОЛНЫЕ")
    
    total_upgrades = 0
    
    for waiter_num in schedule_df['waiter_num'].unique():
        waiter_data = schedule_df[schedule_df['waiter_num'] == waiter_num]
        
        for month in complete_months:
            if month not in hours_by_waiter_month.columns:
                continue
            
            current_hours = hours_by_waiter_month.loc[waiter_num, month] if waiter_num in hours_by_waiter_month.index else 0
            target_hours = target_hours_per_month
            gap = target_hours - current_hours
            
            if gap < 3:
                continue
            
            month_mask = waiter_data['month'] == month
            partial_shifts = waiter_data[
                month_mask & 
                (waiter_data['shift_type_code'].isin([2, 3]))
            ].copy()
            
            if len(partial_shifts) == 0:
                continue
            
            partial_shifts['day_guests'] = partial_shifts['date'].apply(
                lambda d: df[df['date'] == d]['guests'].max() if len(df[df['date'] == d]) > 0 else 0
            )
            partial_shifts = partial_shifts.sort_values('day_guests', ascending=False)
            
            for idx, row in partial_shifts.iterrows():
                if gap <= 0:
                    break
                
                current_shift_code = row['shift_type_code']
                if current_shift_code == 1:
                    continue
                if row.get('is_pattern_work_day', True) == False:
                    continue
                
                current_hours_shift = row['work_hours']
                new_hours = 12
                hours_added = new_hours - current_hours_shift
                
                mask = (schedule_df['waiter_num'] == waiter_num) & (schedule_df['date'] == row['date'])
                schedule_df.loc[mask, 'shift_type_code'] = 1
                schedule_df.loc[mask, 'shift_type'] = 'Полная'
                schedule_df.loc[mask, 'work_hours'] = 12
                
                gap -= hours_added
                total_upgrades += 1
                
                if verbose and total_upgrades <= 5:
                    print(f"   Официант {waiter_num}: {row['date']} — "
                          f"{row['shift_type']} ({current_hours_shift}ч) -> "
                          f"Полная (12ч) [+{hours_added}ч]")
    
    if verbose and total_upgrades > 0:
        print(f"   Всего заменено смен: {total_upgrades}")
    
    return schedule_df


# ОПТИМИЗАЦИЯ СДВИГОВ ДЛЯ ГАРАНТИРОВАННОГО ПОКРЫТИЯ

def optimize_offsets_for_coverage(waiter_patterns, date_list, min_per_day=5, verbose=True):
    num_waiters = len(waiter_patterns)
    
    # Начальные сдвиги: циклические
    offsets = {}
    for w in range(num_waiters):
        pattern_name = waiter_patterns[w]
        cycle = PATTERNS[pattern_name]['cycle']
        offsets[w] = (w * 2) % cycle
    
    # Жадная оптимизация
    improved = True
    max_iterations = 30
    iteration = 0
    
    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        
        for w in range(num_waiters):
            pattern_name = waiter_patterns[w]
            cycle = PATTERNS[pattern_name]['cycle']
            current_offset = offsets[w]
            
            best_offset = current_offset
            best_min_coverage = -1
            
            # Пробуем все возможные сдвиги для этого официанта
            for test_offset in range(cycle):
                daily_counts = []
                for day_idx, date in enumerate(date_list):
                    count = 0
                    for other_w in range(num_waiters):
                        other_pattern = PATTERNS[waiter_patterns[other_w]]
                        other_cycle = other_pattern['cycle']
                        other_work = other_pattern['work']
                        other_offset = offsets[other_w] if other_w != w else test_offset
                        
                        pos = (day_idx + other_offset) % other_cycle
                        if pos < other_work:
                            count += 1
                    daily_counts.append(count)
                
                min_cov = min(daily_counts)
                
                if min_cov > best_min_coverage:
                    best_min_coverage = min_cov
                    best_offset = test_offset
            
            if best_offset != current_offset:
                offsets[w] = best_offset
                improved = True
                if verbose and iteration == 1:
                    print(f"   Официант {w+1}: сдвиг {current_offset} → {best_offset}")
    
    if verbose:
        print(f"   Оптимизация завершена за {iteration} итераций")
    
    return offsets


# АЛГОРИТМ ПЛАНИРОВАНИЯ (УПРОЩЁННЫЙ + ГАРАНТИРОВАННОЕ ПОКРЫТИЕ)

def create_waiter_schedule_algorithm(
    forecast_df: pd.DataFrame,
    min_hours_per_month: int = TARGET_HOURS_PER_MONTH,
    novice_ratio: float = NOVICE_RATIO,
    verbose: bool = True,
    output_path: Optional[str] = None 
) -> Tuple[pd.DataFrame, Dict]: 
    # ПОДГОТОВКА ДАННЫХ
    
    df = forecast_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['hour'] = df['datetime'].dt.hour
    
    guest_col = 'guests_with_buffer' if 'guests_with_buffer' in df.columns else 'guests_predicted'
    df['guests'] = df[guest_col].fillna(0).astype(int)
    
    num_days = df['date'].nunique()
    date_list = sorted(df['date'].unique())
    num_months = num_days / 30.0
    
    if verbose:
        print(f"\nПЛАНИРОВАНИЕ СМЕН ОФИЦИАНТОВ (УПРОЩЁННЫЙ АЛГОРИТМ)")
        print(f"Период: {num_days} дней (~{num_months:.1f} месяцев)")
        print(f"Минимум официантов: {MIN_WAITERS}")
    
    # ШАГ 1: Определяем количество официантов
    
    peak_guests = df['guests'].max()
    min_by_peak = max(MIN_WAITERS, int(np.ceil(peak_guests / 10)))
    
    total_guests = df['guests'].sum()
    total_hours_needed = int(np.ceil(total_guests / 7.5))
    hours_per_waiter = min_hours_per_month * num_months
    min_by_hours = max(MIN_WAITERS, int(np.ceil(total_hours_needed / hours_per_waiter)))
    
    num_waiters = max(min_by_peak, min_by_hours, MIN_WAITERS)
    
    # Увеличили запас для гарантированного покрытия
    num_waiters = int(num_waiters * 2.0)
    num_waiters = max(num_waiters, MIN_WAITERS, 12)
    
    if verbose:
        print(f"Официантов: {num_waiters}")
    
    # ШАГ 2: РАСПРЕДЕЛЕНИЕ ПАТТЕРНОВ + ОПТИМИЗАЦИЯ СДВИГОВ
    
    pattern_names = list(PATTERNS.keys())
    
    preferred_patterns = ['4_2', '4_3', '3_2']
    selected_patterns = [p for p in preferred_patterns if p in pattern_names]
    
    # Циклическое распределение паттернов
    waiter_patterns = {}
    for w in range(num_waiters):
        waiter_patterns[w] = selected_patterns[w % len(selected_patterns)]
    
    if verbose:
        print(f"\nПаттерны ({len(selected_patterns)} разных):")
        for p in selected_patterns:
            count = sum(1 for w in waiter_patterns.values() if w == p)
            print(f"   {p}: {count} официантов")
    
    # ОПТИМИЗАЦИЯ СДВИГОВ для гарантированного покрытия
    if verbose:
        print(f"\nОптимизация сдвигов для минимума {MIN_WAITERS} официантов/день...")
    
    optimized_offsets = optimize_offsets_for_coverage(
        waiter_patterns, date_list, 
        min_per_day=MIN_WAITERS, verbose=verbose
    )
    
    # ШАГ 3: Создаём расписание по паттернам (С ОПТИМИЗИРОВАННЫМИ СДВИГАМИ)
    
    schedule_data = []
    
    num_novices = int(np.ceil(num_waiters * novice_ratio))
    num_specialists = num_waiters - num_novices
    
    for w in range(num_waiters):
        waiter_type = 'Новичок' if w >= num_specialists else 'Специалист'
        waiter_type_code = 2 if waiter_type == 'Новичок' else 1
        
        pattern_name = waiter_patterns[w]
        pattern = PATTERNS[pattern_name]
        cycle = pattern['cycle']
        work_days = pattern['work']
        rest_days = pattern['rest']
        
        # ИСПОЛЬЗУЕМ оптимизированный сдвиг
        offset = optimized_offsets[w]
        
        for day_idx, date in enumerate(date_list):
            pos_in_cycle = (day_idx + offset) % cycle
            is_work_day = pos_in_cycle < work_days
            
            if is_work_day:
                day_data = df[df['date'] == date]
                shift_type = get_shift_type_by_hourly_demand(day_data, verbose=False)
                shift_info = SHIFT_TYPES[shift_type]
                work_hours = shift_info['hours']
                shift_code = shift_info['code']
                shift_name = shift_info['name']
            else:
                shift_type = 'off'
                work_hours = 0
                shift_code = 0
                shift_name = 'Выходной'
            
            day_guests = df[df['date'] == date]['guests'].max() if len(df[df['date'] == date]) > 0 else 0
            
            schedule_data.append({
                'date': date,
                'waiter_id': f'Официант {w+1}',
                'waiter_num': w+1,
                'waiter_type': waiter_type,
                'waiter_type_code': waiter_type_code,
                'waiter_capacity': 10 if waiter_type == 'Специалист' else 5,
                'shift_type_code': shift_code,
                'shift_type': shift_name,
                'work_hours': work_hours,
                'guests_predicted': int(day_guests),
                'is_pattern_work_day': is_work_day,
                'pattern_name': pattern_name,
            })
    
    schedule_df = pd.DataFrame(schedule_data)
    
    # ШАГ 4: ПРОВЕРКИ И КОРРЕКТИРОВКИ (БЕЗ НАРУШЕНИЯ ПАТТЕРНОВ)
    
    if verbose:
        print("\nПРОВЕРКИ КАЧЕСТВА РАСПИСАНИЯ")
    
    # Проверка 1: Покрытие нагрузки
    coverage_ok, gaps_df = check_hourly_coverage(schedule_df, df, verbose=verbose)
    
    # Проверка 2: Минимум официантов
    min_waiters_ok, days_with_gaps = ensure_min_waiters_per_day(
        schedule_df, df, min_per_day=5, verbose=verbose
    )
    
    # Проверка 3: Максимум дней подряд
    consecutive_ok, consecutive_violations = check_max_consecutive_days(
        schedule_df, max_consecutive=MAX_CONSECUTIVE_DAYS, verbose=verbose
    )
    
    # Проверка 4: Балансировка
    target_hours = min_hours_per_month * num_months
    balance_ok, balance_info = balance_hours(schedule_df, target_hours=target_hours, verbose=verbose)
    
    # Корректировка часов: замена на полные (НЕ меняет выходные!)
    if verbose:
        print(f"\nКорректировка часов (замена на полные смены)...")
    
    schedule_df = upgrade_shifts_to_full(
        schedule_df, df, 
        target_hours_per_month=min_hours_per_month, 
        verbose=verbose
    )
    
    # Снижение переработки (НЕ меняет выходные!)
    if verbose:
        print(f"\nКорректировка часов (снижение переработки)...")
    
    schedule_df = reduce_overtime(
        schedule_df, df,
        target_hours=min_hours_per_month,
        max_overtime_pct=0.15,
        verbose=verbose
    )
    
    # ФИНАЛЬНАЯ ПРОВЕРКА ПОКРЫТИЯ
    
    if verbose:
        print(f"\nФИНАЛЬНАЯ ПРОВЕРКА ПОКРЫТИЯ:")
        daily_count = schedule_df.groupby('date').apply(
            lambda x: (x['shift_type_code'] > 0).sum()
        )
        
        min_cov = daily_count.min()
        max_cov = daily_count.max()
        avg_cov = daily_count.mean()
        low_days = (daily_count < MIN_WAITERS).sum()
        
        print(f"   Мин: {min_cov}, Макс: {max_cov}, Среднее: {avg_cov:.1f}")
        print(f"   Дней с <{MIN_WAITERS} официантами: {low_days}")
        
        if low_days > 0:
            print(f"   Примеры проблемных дней:")
            for date, count in daily_count[daily_count < MIN_WAITERS].head(3).items():
                working = schedule_df[
                    (schedule_df['date'] == date) & 
                    (schedule_df['shift_type_code'] > 0)
                ]['waiter_num'].tolist()
                print(f"      {date}: {count} работающих [{working}]")
            print(f"   Если нужно 0 дней с <{MIN_WAITERS}, увеличьте multiplier до 2.2")
        else:
            print(f"   ГАРАНТИЯ ВЫПОЛНЕНА: все дни имеют >= {MIN_WAITERS} официантов")
    
    # ШАГ 5: Статистика
    
    total_hours = schedule_df['work_hours'].sum()
    
    shifts_per_waiter = schedule_df.groupby('waiter_num').apply(
        lambda x: pd.Series({
            'total_shifts': (x['shift_type_code'] > 0).sum(),
            'full_shifts': (x['shift_type_code'] == 1).sum(),
            'morning_shifts': (x['shift_type_code'] == 2).sum(),
            'evening_shifts': (x['shift_type_code'] == 3).sum(),
        })
    ).to_dict('index')
    
    stats = {
        'num_waiters': num_waiters,
        'num_specialists': num_specialists,
        'num_novices': num_novices,
        'total_hours': int(total_hours),
        'total_shifts': int((schedule_df['shift_type_code'] > 0).sum()),
        'avg_hours_per_waiter': float(total_hours / num_waiters) if num_waiters > 0 else 0,
        'waiter_patterns': {w+1: p for w, p in waiter_patterns.items()},
        'coverage_ok': coverage_ok,
        'min_waiters_ok': min_waiters_ok,
        'consecutive_ok': consecutive_ok,
        'balance_ok': balance_ok,
    }
    
    if verbose:
        print(f"\nИТОГОВАЯ СТАТИСТИКА")
        print(f"Расписание создано!")
        print(f"   Всего часов: {total_hours}")
        print(f"   Часов/официант: {stats['avg_hours_per_waiter']:.1f}")
        print(f"   Покрытие: {'' if coverage_ok else ''}")
        print(f"   Мин. официантов/день: {'' if min_waiters_ok else ''}")
        print(f"   Макс. дней подряд: {'' if consecutive_ok else ''}")
    
    # ШАГ 6: СОХРАНЕНИЕ
    
    if output_path and not schedule_df.empty:
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        schedule_df.to_csv(output_path_obj, index=False, encoding='utf-8-sig')
        if verbose:
            print(f"\nРасписание сохранено: {output_path}")
    
    return schedule_df, stats