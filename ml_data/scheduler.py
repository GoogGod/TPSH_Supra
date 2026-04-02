import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
from pathlib import Path
from typing import Tuple, Dict, List


# КОНФИГУРАЦИЯ

WAITER_TYPES = {
    'pro': {
        'name': 'Профессионал',
        'capacity': 10,  # гостей в час
        'code': 1
    },
    'noob': {
        'name': 'Новичок',
        'capacity': 5,   # гостей в час
        'code': 2
    }
}

SHIFT_TYPES = {
    'full': {
        'name': 'Полная',
        'start': 9,
        'end': 22,    
        'hours': 12,
        'code': 1
    },
    'morning': {
        'name': 'Утренняя',
        'start': 9,
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
        min_waiters_per_shift: int = 5,
        max_work_hours_per_week: int = 48,
        min_days_off_per_week: int = 1
    ):
        self.min_waiters_per_shift = min_waiters_per_shift
        self.max_work_hours_per_week = max_work_hours_per_week
        
        self.working_hour_start = 10
        self.working_hour_end = 23
    
    def calculate_waiters_needed(
        self, 
        forecast_df: pd.DataFrame,
        waiter_config: Dict[int, str]
    ) -> pd.DataFrame:
        df = forecast_df.copy()

        # Вместимость по типам официантов
        capacities = {
            'pro': 10,
            'noob': 5
        }

        # Средняя вместимость одного официанта в бригаде
        avg_capacity = np.mean([capacities[t] for t in waiter_config.values()])

        # Используем гостей с буфером
        if 'guests_with_buffer' in df.columns:
            guests_column = 'guests_with_buffer'
        else:
            guests_column = 'guests_predicted'

        # Количество официантов = гости / средняя вместимость
        df['waiters_needed'] = np.ceil(
            df[guests_column] / avg_capacity
        ).astype(int)

        # МИНИМУМ 5 ОФИЦИАНТОВ В РАБОЧИЕ ЧАСЫ
        working_mask = (df['hour'] >= self.working_hour_start) & \
                       (df['hour'] < self.working_hour_end)

        # Устанавливаем минимум 5 официантов
        df.loc[working_mask, 'waiters_needed'] = df.loc[
            working_mask, 'waiters_needed'
        ].clip(lower=self.min_waiters_per_shift) 

        # Вне рабочих часов — 0 официантов
        df.loc[~working_mask, 'waiters_needed'] = 0

        return df
    
    def calculate_daily_shift_requirements(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Извлекаем дату из datetime
        df['date'] = pd.to_datetime(df['datetime']).dt.date

        # Группируем по дате и часу, берём максимум waiters_needed
        daily_hourly = df.groupby(['date', 'hour'])['waiters_needed'].max().reset_index()

        # Используем только существующие колонки
        agg_dict = {
            'waiters_max': ('waiters_needed', 'max'),
            'waiters_mean': ('waiters_needed', 'mean'),
        }

        # Добавляем guests_with_buffer только если колонка существует
        if 'guests_with_buffer' in daily_hourly.columns:
            agg_dict['total_guests'] = ('guests_with_buffer', 'sum')
        elif 'guests_predicted' in df.columns:
            # Берём из исходного df, сгруппированного по дате
            daily_guests = df.groupby('date')['guests_predicted'].sum().reset_index()
            daily_guests.columns = ['date', 'total_guests']
            agg_dict['total_guests'] = ('waiters_needed', 'count')  # заглушка

        daily_req = daily_hourly.groupby('date').agg(**agg_dict).reset_index()

        # Добавляем потребность по сменам
        daily_req['morning_need'] = daily_req['waiters_max']
        daily_req['evening_need'] = daily_req['waiters_max']
        daily_req['total_waiters_needed'] = daily_req['waiters_max']

        return daily_req
    
    def create_schedule(
        self,
        forecast_df: pd.DataFrame,
        waiter_config: Dict[int, str],
        verbose: bool = True
    ) -> Tuple[pd.DataFrame, Dict]:
        if verbose:
            print("ПЛАНИРОВАНИЕ СМЕН ОФИЦИАНТОВ")
        
        # Копируем forecast_df, а не df
        df = forecast_df.copy()
        
        # Извлекаем дату и час
        df['date'] = pd.to_datetime(df['datetime']).dt.date
        df['hour'] = df['datetime'].dt.hour
        
        # Рассчитываем потребность в официантах
        df = self.calculate_waiters_needed(df, waiter_config)
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
        
        # Адаптивная минимальная выработка
        min_hours_per_waiter = int(MIN_HOURS_PER_MONTH * num_days / 30)
        
        max_possible_hours = estimated_total_hours
        min_required_total = min_hours_per_waiter * num_waiters
        
        # Если требование превышает возможное — снижаем пропорционально
        if min_required_total > max_possible_hours * 1.5:
            scale_factor = (max_possible_hours * 1.5) / min_required_total
            min_hours_per_waiter = int(min_hours_per_waiter * scale_factor)
            if verbose:
                print(f"\nПотребность низкая — мин. выработка снижена:")
                print(f"   Было: {int(MIN_HOURS_PER_MONTH * num_days / 30)}ч")
                print(f"   Стало: {min_hours_per_waiter}ч (масштаб: {scale_factor:.2f})")
        
        # Целевое количество часов
        target_hours = max(min_hours_per_waiter, estimated_total_hours // num_waiters)
        
        if verbose:
            print(f"\nЦелевые показатели:")
            print(f"   Общая потребность: ~{estimated_total_hours} часов")
            print(f"   Минимум часов/официант: {min_hours_per_waiter}")
            print(f"   Целевое часов/официант: ~{target_hours}")
        
        # Создаём модель оптимизации
        model = cp_model.CpModel()
        
        # ПЕРЕМЕННЫЕ: shift[(waiter, day, shift_type)] = BoolVar
        shift = {}
        for w in range(1, num_waiters + 1):
            for d in range(num_days):
                for s in [1, 2, 3]:  # 1=Полная, 2=Утренняя, 3=Вечерняя
                    shift[(w, d, s)] = model.NewBoolVar(f'shift_w{w}_d{d}_s{s}')
        
        # Переменные для часов работы каждого официанта
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
        
        # 1. Одна смена в день максимум
        for w in range(1, num_waiters + 1):
            for d in range(num_days):
                model.Add(sum(shift[(w, d, s)] for s in [1, 2, 3]) <= 1)
        
        # 2. Покрытие потребности в официантах (упрощённо)
        for d in range(num_days):
            day_need = daily_req.loc[daily_req['date'] == date_list[d], 'waiters_max'].values
            need = int(day_need[0]) if len(day_need) > 0 else self.min_waiters_per_shift
            
            # Считаем покрытие: каждый Профессионал = 2 "единицы", новичок = 1
            coverage = sum(
                (2 if waiter_config[w] == 'pro' else 1) * 
                sum(shift[(w, d, s)] for s in [1, 2, 3])
                for w in range(1, num_waiters + 1)
            )
            
            # Требуемое покрытие в "единицах"
            required = need * 2  # консервативно: считаем всех как новичков
            
            model.Add(coverage >= required)
        
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
        
        # ЦЕЛЕВАЯ ФУНКЦИЯ: минимизировать дисбаланс часов
        
        # 1. Одна смена в день максимум
        for w in range(1, num_waiters + 1):
            for d in range(num_days):
                model.Add(sum(shift[(w, d, s)] for s in [1, 2, 3]) <= 1)
        
        # 2. Покрытие потребности (упрощённо)
        for d in range(num_days):
            day_need = daily_req.loc[daily_req['date'] == date_list[d], 'waiters_max'].values
            need = int(day_need[0]) if len(day_need) > 0 else self.min_waiters_per_shift
            
            coverage = sum(
                (2 if waiter_config[w] == 'pro' else 1) * 
                sum(shift[(w, d, s)] for s in [1, 2, 3])
                for w in range(1, num_waiters + 1)
            )
            
            required = need * 2
            model.Add(coverage >= required)
        
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
        
        # 6. Ограничение: минимум 50% полных смен (было 70%)
        for w in range(1, num_waiters + 1):
            total_shifts_w = sum(shift[(w, d, s)] for d in range(num_days) for s in [1, 2, 3])
            full_shifts_w = sum(shift[(w, d, 1)] for d in range(num_days))
            
            # Полные смены >= 50% от всех смен
            model.Add(full_shifts_w * 2 >= total_shifts_w)
        
        # 7. Ограничение: максимум 30% утренних смен (было 20%)
        for w in range(1, num_waiters + 1):
            total_shifts_w = sum(shift[(w, d, s)] for d in range(num_days) for s in [1, 2, 3])
            morning_shifts_w = sum(shift[(w, d, 2)] for d in range(num_days))
            
            # Утренние <= 30% от всех смен
            model.Add(morning_shifts_w * 10 <= total_shifts_w * 3)
        
        # 8. Ограничение: максимум 30% вечерних смен (было 20%)
        for w in range(1, num_waiters + 1):
            total_shifts_w = sum(shift[(w, d, s)] for d in range(num_days) for s in [1, 2, 3])
            evening_shifts_w = sum(shift[(w, d, 3)] for d in range(num_days))
            
            # Вечерние <= 30% от всех смен
            model.Add(evening_shifts_w * 10 <= total_shifts_w * 3)
        
        # ЦЕЛЕВАЯ ФУНКЦИЯ: только баланс часов (без штрафов за тип смены)
        
        imbalance_vars = []
        for w in range(1, num_waiters + 1):
            deviation = model.NewIntVar(0, num_days * 13, f'deviation_w{w}')
            model.AddAbsEquality(deviation, waiter_hours[w] - target_hours)
            imbalance_vars.append(deviation)
        
        total_imbalance = sum(imbalance_vars)
        
        # Минимизируем только дисбаланс часов
        model.Minimize(total_imbalance)
        
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
        else:
            if verbose:
                print(f"{solver.StatusName(status)}: не удалось найти решение")
            return None, {}
        
        # СОЗДАНИЕ РАСПИСАНИЯ
        
        schedule_data = []
        
        # Словарь для быстрого доступа по коду смены
        SHIFT_INFO = {
            1: {'name': 'Полная', 'start': 10, 'end': 22, 'hours': 12},
            2: {'name': 'Утренняя', 'start': 10, 'end': 16, 'hours': 6},
            3: {'name': 'Вечерняя', 'start': 16, 'end': 25, 'hours': 9},
        }
        
        for w in range(1, num_waiters + 1):
            waiter_type = waiter_config[w]
            
            for d in range(num_days):
                shift_type_code = 0
                shift_name = 'Выходной'
                work_start = None
                work_end = None
                work_hours = 0
                
                # Определяем назначенную смену
                for s in [1, 2, 3]:
                    if solver.Value(shift[(w, d, s)]) == 1:
                        shift_type_code = s
                        shift_name = SHIFT_INFO[s]['name']
                        work_start = SHIFT_INFO[s]['start']
                        work_end = SHIFT_INFO[s]['end']
                        work_hours = SHIFT_INFO[s]['hours']
                        break
                
                # Потребность в этот день
                day_req = daily_req[daily_req['date'] == date_list[d]]
                waiters_needed = int(day_req['waiters_max'].values[0]) if len(day_req) > 0 else self.min_waiters_per_shift
                
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
                    'waiters_needed': waiters_needed
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
            print(f"     Полных: {stats['full_shifts']}")
            print(f"     Утренних: {stats['morning_shifts']}")
            print(f"     Вечерних: {stats['evening_shifts']}")
            print(f"   Всего часов: {stats['total_hours']}")
            print(f"   Часов на официанта: {stats['avg_hours_per_waiter']:.1f}")
            print(f"   Минимум {min_hours_per_waiter}ч: {'1' if stats['min_hours_met'] else '0'}")
        
        return schedule_df, stats
    
    def print_schedule_summary(self, schedule_df: pd.DataFrame, min_hours: int):        
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
    forecast_path: str,
    waiter_config: Dict[int, str],
    output_path: str = None,
    min_waiters_per_shift: int = 5,
    max_hours_per_month: int = 200,
    verbose: bool = True
) -> Tuple[pd.DataFrame, Dict]:
    # Загружаем прогноз
    if verbose:
        print(f"Загрузка прогноза из: {forecast_path}")
    
    forecast_df = pd.read_csv(forecast_path, parse_dates=['datetime'])
    
    if verbose:
        print(f"Конфигурация официантов: {waiter_config}")
    
    # Создаём планировщик
    scheduler = WaiterScheduler(
        min_waiters_per_shift=min_waiters_per_shift
    )
    
    # Создаём расписание
    schedule_df, stats = scheduler.create_schedule(
        forecast_df=forecast_df,
        waiter_config=waiter_config,
        verbose=verbose
    )
    
    if schedule_df is None or len(schedule_df) == 0:
        if verbose:
            print(f"\nНе удалось создать расписание — пропускаем сохранение")
        return pd.DataFrame(), {}
    
    # Сохраняем расписание
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        schedule_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        if verbose:
            print(f"\nРасписание сохранено: {output_path}")
    
    return schedule_df, stats


if __name__ == '__main__':
    # Тестовая конфигурация
    waiter_config = {
        1: 'pro',
        2: 'pro',
        3: 'pro',
        4: 'noob',
        5: 'noob'
    }
    
    schedule_df, stats = create_waiter_schedule(
        forecast_path='data/predicted/forecast.csv',
        waiter_config=waiter_config,
        output_path='data/predicted/waiter_schedule.csv',
        verbose=True
    )