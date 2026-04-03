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
    '2_2': {'work': 2, 'rest': 2, 'cycle': 4},
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


# ПРОВЕРКИ И УЛУЧШЕНИЯ

def check_hourly_coverage(schedule_df, forecast_df, verbose=True):
    """Проверяет, хватает ли официантов в каждый час"""
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
        print(f"   Покрытие ≥100%: {coverage_rate:.1f}%")
        
        if len(gaps) > 0:
            print(f"    Найдено {len(gaps)} часов с недостаточным покрытием!")
            
            worst_gaps = gaps.nsmallest(5, 'coverage_ratio')
            for _, row in worst_gaps.iterrows():
                print(f"      {row['date']} {row['hour']:02d}:00 — "
                      f"{row['waiter_capacity']:.0f} из {row['needed']:.0f} "
                      f"({row['coverage_ratio']*100:.0f}%)")
    
    return len(gaps) == 0, gaps


def get_shift_type_by_hourly_demand(day_data, verbose=False):
    """Выбирает тип смены по пиковому часу, а не по дню"""
    if len(day_data) == 0:
        return 'morning'
    
    peak_hour_guests = day_data.groupby('hour')['guests'].max().max()
    avg_guests = day_data['guests'].mean()
    
    if peak_hour_guests > 15 or avg_guests > 8:  # Было >20 / >12
        return 'full'      # 12 часов
    elif peak_hour_guests > 8 or avg_guests > 4:  # Было >10 / >6
        return 'evening'   # 9 часов
    else:
        return 'morning'   # 6 часов


def ensure_min_waiters_per_day(schedule_df, forecast_df, min_per_day=5, verbose=True):
    """Гарантирует что каждый день работает минимум N официантов"""
    daily_count = schedule_df.groupby('date').apply(
        lambda x: (x['shift_type_code'] > 0).sum()
    )
    
    days_with_gaps = daily_count[daily_count < min_per_day]
    
    if verbose and len(days_with_gaps) > 0:
        print(f"\nНайдено {len(days_with_gaps)} дней с <{min_per_day} официантами:")
        for date, count in days_with_gaps.head(5).items():
            print(f"   {date}: {count} официантов")
    
    return len(days_with_gaps) == 0, days_with_gaps


def balance_hours(schedule_df, target_hours=200, tolerance=0.2, verbose=True):
    """Проверяет балансировку часов между официантами"""
    hours_per_waiter = schedule_df.groupby('waiter_num')['work_hours'].sum()
    
    avg_hours = hours_per_waiter.mean()
    min_hours = hours_per_waiter.min()
    max_hours = hours_per_waiter.max()
    
    over = hours_per_waiter[hours_per_waiter > target_hours * (1 + tolerance)]
    under = hours_per_waiter[hours_per_waiter < target_hours * (1 - tolerance)]
    
    if verbose:
        print(f"\nБалансировка часов:")
        print(f"   Среднее: {avg_hours:.1f}ч")
        print(f"   Мин: {min_hours:.1f}ч, Макс: {max_hours:.1f}ч")
        print(f"   Разброс: {max_hours - min_hours:.1f}ч")
        
        if len(over) > 0:
            print(f"   {len(over)} официантов работают больше нормы")
        if len(under) > 0:
            print(f"   {len(under)} официантов работают меньше нормы")
    
    is_balanced = len(over) == 0 and len(under) == 0
    return is_balanced, {'over': over, 'under': under, 'avg': avg_hours}


def add_extra_shifts(schedule_df, forecast_df, gaps_df, verbose=True):
    if len(gaps_df) == 0:
        return schedule_df, 0
    
    schedule_df = schedule_df.copy()
    extra_shifts_added = 0
    
    for _, gap in gaps_df.iterrows():
        gap_date = gap['date']
        gap_hour = gap['hour']
        needed = gap['needed'] - gap['waiter_capacity']
        
        # Найти официантов у которых выходной в этот день
        off_duty = schedule_df[
            (schedule_df['date'] == gap_date) & 
            (schedule_df['shift_type_code'] == 0)
        ]['waiter_num'].unique()
        
        if len(off_duty) > 0:
            # Назначить смену первому доступному
            waiter_num = off_duty[0]
            mask = (schedule_df['date'] == gap_date) & (schedule_df['waiter_num'] == waiter_num)
            schedule_df.loc[mask, 'shift_type_code'] = 3  # Evening
            schedule_df.loc[mask, 'shift_type'] = 'Вечерняя'
            schedule_df.loc[mask, 'work_hours'] = 9
            
            extra_shifts_added += 1
            
            if verbose and extra_shifts_added <= 3:
                print(f"   Добавлена смена: Официант {waiter_num}, {gap_date}, {gap_hour:02d}:00")
    
    if verbose and extra_shifts_added > 0:
        print(f"   Всего добавлено смен: {extra_shifts_added}")
    
    return schedule_df, extra_shifts_added


def upgrade_shifts_to_full(schedule_df, forecast_df, target_hours_per_month=200, verbose=True):
    df = forecast_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['month'] = df['datetime'].dt.to_period('M')
    
    schedule_df = schedule_df.copy()
    schedule_df['date'] = pd.to_datetime(schedule_df['date']).dt.date
    schedule_df['month'] = pd.to_datetime(schedule_df['date']).dt.to_period('M')
    
    # ИСКЛЮЧАЕМ неполные месяцы (где < 25 дней данных)
    days_per_month = schedule_df.groupby('month')['date'].nunique()
    complete_months = days_per_month[days_per_month >= 25].index.tolist()
    
    if len(complete_months) == 0:
        complete_months = schedule_df['month'].unique().tolist()
    
    if verbose:
        print(f"\nПолные месяцы для расчёта: {', '.join(map(str, complete_months))}")
    
    hours_by_waiter_month = schedule_df.groupby(['waiter_num', 'month'])['work_hours'].sum().unstack(fill_value=0)
    
    if verbose:
        print("УВЕЛИЧЕНИЕ ЧАСОВ ЧЕРЕЗ ЗАМЕНУ СМЕН НА ПОЛНЫЕ")
    
    total_upgrades = 0
    upgrades_by_waiter = {}
    
    for waiter_num in schedule_df['waiter_num'].unique():
        waiter_data = schedule_df[schedule_df['waiter_num'] == waiter_num]
        upgrades_by_waiter[waiter_num] = 0
        
        for month in complete_months:  # Только полные месяцы
            if month not in hours_by_waiter_month.columns:
                continue
            
            current_hours = hours_by_waiter_month.loc[waiter_num, month] if waiter_num in hours_by_waiter_month.index else 0
            target_hours = target_hours_per_month
            gap = target_hours - current_hours
            
            # ИСПРАВЛЕНО: Порог снижен с 10 до 5 часов
            if gap < 5:
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
                current_hours_shift = row['work_hours']
                
                if current_shift_code == 1:
                    continue
                
                new_hours = 12
                hours_added = new_hours - current_hours_shift
                
                mask = (schedule_df['waiter_num'] == waiter_num) & (schedule_df['date'] == row['date'])
                schedule_df.loc[mask, 'shift_type_code'] = 1
                schedule_df.loc[mask, 'shift_type'] = 'Полная'
                schedule_df.loc[mask, 'work_hours'] = 12
                
                gap -= hours_added
                total_upgrades += 1
                upgrades_by_waiter[waiter_num] += 1
                
                if verbose and total_upgrades <= 5:
                    print(f"   Официант {waiter_num}: {row['date']} — "
                          f"{row['shift_type']} ({current_hours_shift}ч) → "
                          f"Полная (12ч) [+{hours_added}ч]")
    
    if verbose:
        if total_upgrades > 0:
            print(f"\n   Всего заменено смен: {total_upgrades}")
            for w, count in upgrades_by_waiter.items():
                if count > 0:
                    print(f"      Официант {w}: {count} смен")
        else:
            print(f"\n   ℹЗамен не требуется — все в норме")
    
    return schedule_df


def enforce_200_hours_per_month(schedule_df, forecast_df, target=200, verbose=True):
    df = forecast_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['month'] = df['datetime'].dt.to_period('M')
    
    schedule_df = schedule_df.copy()
    schedule_df['date'] = pd.to_datetime(schedule_df['date']).dt.date
    schedule_df['month'] = pd.to_datetime(schedule_df['date']).dt.to_period('M')
    
    # Исключаем неполные месяцы
    days_per_month = schedule_df.groupby('month')['date'].nunique()
    complete_months = days_per_month[days_per_month >= 25].index.tolist()
    
    if len(complete_months) == 0:
        return schedule_df
    
    if verbose:
        print("ПРИНУДИТЕЛЬНОЕ ОБЕСПЕЧЕНИЕ 200 ЧАСОВ/МЕС")
    
    total_changes = 0
    
    for waiter_num in schedule_df['waiter_num'].unique():
        waiter_data = schedule_df[schedule_df['waiter_num'] == waiter_num]
        
        for month in complete_months:
            month_mask = waiter_data['month'] == month
            current_hours = waiter_data[month_mask]['work_hours'].sum()
            gap = target - current_hours
            
            # Если уже норма — пропускаем этого официанта в этом месяце
            if gap <= 0:
                if verbose:
                    print(f"\n   Официант {waiter_num}, {month}: {current_hours}ч — уже норма")
                continue
            
            if verbose:
                print(f"\n   Официант {waiter_num}, {month}: {current_hours}ч → нужно {target}ч (недобор {gap}ч)")
            
            # ШАГ 1: Заменять частичные смены на полные ПОКА gap > 0
            
            partial_shifts = waiter_data[
                month_mask & 
                (waiter_data['shift_type_code'].isin([2, 3]))
            ].copy()
            
            # Сортируем по нагрузке (сначала дни с высокой нагрузкой)
            partial_shifts['day_guests'] = partial_shifts['date'].apply(
                lambda d: df[df['date'] == d]['guests'].max() if len(df[df['date'] == d]) > 0 else 0
            )
            partial_shifts = partial_shifts.sort_values('day_guests', ascending=False)
            
            for idx, row in partial_shifts.iterrows():
                # КЛЮЧЕВОЕ: выходим если gap закрыт
                if gap <= 0:
                    if verbose:
                        print(f"      Норма достигнута, останавливаем замены")
                    break
                
                current_hours_shift = row['work_hours']
                hours_added = 12 - current_hours_shift
                
                mask = (schedule_df['waiter_num'] == waiter_num) & (schedule_df['date'] == row['date'])
                schedule_df.loc[mask, 'shift_type_code'] = 1
                schedule_df.loc[mask, 'shift_type'] = 'Полная'
                schedule_df.loc[mask, 'work_hours'] = 12
                
                gap -= hours_added
                total_changes += 1
                
                if verbose and total_changes <= 10:
                    print(f"      {row['date']}: {row['shift_type']} ({current_hours_shift}ч) → Полная (12ч) [+{hours_added}ч], недобор: {max(0, gap)}ч")
            
            # ШАГ 2: Если всё ещё недобор — добавить смены в выходные (только пока gap > 0)
            
            if gap > 0:
                if verbose:
                    print(f"      После замены всё ещё недобор {gap}ч — добавляем смены в выходные...")
                
                off_days = waiter_data[
                    month_mask & 
                    (waiter_data['shift_type_code'] == 0)
                ].copy()
                
                off_days['day_guests'] = off_days['date'].apply(
                    lambda d: df[df['date'] == d]['guests'].max() if len(df[df['date'] == d]) > 0 else 0
                )
                off_days = off_days.sort_values('day_guests', ascending=False)
                
                for idx, row in off_days.iterrows():
                    # КЛЮЧЕВОЕ: выходим если gap закрыт
                    if gap <= 0:
                        break
                    
                    mask = (schedule_df['waiter_num'] == waiter_num) & (schedule_df['date'] == row['date'])
                    schedule_df.loc[mask, 'shift_type_code'] = 3
                    schedule_df.loc[mask, 'shift_type'] = 'Вечерняя'
                    schedule_df.loc[mask, 'work_hours'] = 9
                    
                    gap -= 9
                    total_changes += 1
                    
                    if verbose and total_changes <= 15:
                        print(f"      {row['date']}: Выходной → Вечерняя [+9ч], недобор: {max(0, gap)}ч")
    
    if verbose:
        print(f"\n   Всего изменений: {total_changes}")
    
    return schedule_df

# АЛГОРИТМ ПЛАНИРОВАНИЯ

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
        print(f"\n")
        print("ПЛАНИРОВАНИЕ СМЕН ОФИЦИАНТОВ (УЛУЧШЕННЫЙ АЛГОРИТМ)")
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
    num_waiters = int(num_waiters * 1.3)
    num_waiters = max(num_waiters, MIN_WAITERS, 6)
    
    if verbose:
        print(f"Официантов: {num_waiters}")
        print(f"   По пику: {min_by_peak}")
        print(f"   По часам: {min_by_hours}")
        print(f"   С запасом 30%: {num_waiters}")
    
    # ШАГ 2: Назначаем паттерны официантам
    
    pattern_names = list(PATTERNS.keys())
    waiter_patterns = {}
    
    num_patterns_to_use = min(3, len(pattern_names), num_waiters)
    
    preferred_patterns = ['4_2', '4_3', '3_2']
    selected_patterns = [p for p in preferred_patterns if p in pattern_names]
    
    while len(selected_patterns) < num_patterns_to_use:
        for p in pattern_names:
            if p not in selected_patterns:
                selected_patterns.append(p)
                break
    
    for w in range(num_waiters):
        if w < len(selected_patterns):
            waiter_patterns[w] = selected_patterns[w]
        else:
            waiter_patterns[w] = selected_patterns[w % len(selected_patterns)]
    
    if verbose:
        print(f"\nПаттерны (гарантировано {num_patterns_to_use} разных):")
        for p in selected_patterns:
            count = sum(1 for w in waiter_patterns.values() if w == p)
            print(f"   {p}: {count} официантов")
    
    # ШАГ 3: Создаём расписание по паттернам
    
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
        
        offset = (w * 3) % cycle
        
        for day_idx, date in enumerate(date_list):
            pos_in_cycle = (day_idx - offset) % cycle
            is_work_day = pos_in_cycle < work_days
            
            if is_work_day:
                day_data = df[df['date'] == date]
                
                # Выбор типа смены по пиковому часу
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
                'guests_predicted': int(day_guests)
            })
    
    schedule_df = pd.DataFrame(schedule_data)
    
    # ШАГ 4: ПРОВЕРКИ И КОРРЕКТИРОВКИ
    
    if verbose:
        print("ПРОВЕРКИ КАЧЕСТВА РАСПИСАНИЯ")
    
    # Проверка 1: Почасовое покрытие
    coverage_ok, gaps_df = check_hourly_coverage(schedule_df, df, verbose=verbose)
    
    # Проверка 2: Минимум официантов в день
    min_waiters_ok, days_with_gaps = ensure_min_waiters_per_day(
        schedule_df, df, min_per_day=5, verbose=verbose
    )
    
    # Проверка 3: Балансировка часов
    target_hours = min_hours_per_month * num_months
    balance_ok, balance_info = balance_hours(schedule_df, target_hours=target_hours, verbose=verbose)
    
    # Корректировка: Добавление смен в часы пик
    if not coverage_ok and len(gaps_df) > 0:
        if verbose:
            print(f"\nДобавление дополнительных смен...")
        schedule_df, extra_shifts = add_extra_shifts(
            schedule_df, df, gaps_df, verbose=verbose
        )
        
        if verbose:
            print(f"\nКорректировка часов (замена на полные смены)...")
    
    schedule_df = upgrade_shifts_to_full(
        schedule_df, df, 
        target_hours_per_month=min_hours_per_month, 
        verbose=verbose
    )
    
    schedule_df = enforce_200_hours_per_month(
        schedule_df, df,
        target=200,
        verbose=verbose
    )
    
    # ШАГ 5: Статистика
    
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
        'balance_ok': balance_ok,
        'balance_info': balance_info,
    }
    
    if verbose:
        print(f"\n")
        print("ИТОГОВАЯ СТАТИСТИКА")
        print(f"Расписание создано!")
        print(f"   Всего часов: {total_hours}")
        print(f"   Часов/официант: {stats['avg_hours_per_waiter']:.1f}")
        print(f"   Покрытие часов: {'1' if coverage_ok else '0'}")
        print(f"   Мин. официантов/день: {'1' if min_waiters_ok else '0'}")
        print(f"   Балансировка: {'1' if balance_ok else '0'}")
    
    # ШАГ 6: СОХРАНЕНИЕ РАСПИСАНИЯ
    
    if output_path and not schedule_df.empty:
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        schedule_df.to_csv(output_path_obj, index=False, encoding='utf-8-sig')
        if verbose:
            print(f"\nРасписание сохранено: {output_path}")
    
    return schedule_df, stats
