---

## Activities.md

```markdown
# Инвентаризация Activities — Supra

Полный список сервисных функций, сгруппированный по модулям.

---

## Процессы системы

| Код | Процесс | Триггер |
|-----|---------|---------|
| **АВТ** | Аутентификация (login/logout/refresh) | Действие пользователя |
| **РП** | Регистрация персонала | Менеджер / Админ |
| **ЗД** | Загрузка данных для ML | Менеджер (POST upload-data) |
| **МЛ** | ML-пайплайн (обработка → обучение → прогноз) | Менеджер (POST run) / cron |
| **ГР** | Генерация расписания (OR-Tools) | Менеджер (POST generate-schedule) |
| **ЗГ** | Загрузка CSV расписания (ручная) | Менеджер (POST upload) |
| **ПБ** | Публикация расписания | Менеджер (POST publish) |
| **ЗН** | Занятие позиции сотрудником | Действие сотрудника (POST claim) |
| **НЗ** | Ручное назначение менеджером | Менеджер (POST assign) |
| **ПД** | Подтверждение назначения | Сотрудник (POST confirm/reject) |
| **НП** | Напоминание о расписании | cron (send_schedule_reminders) |

---

## users/views.py — аутентификация и управление пользователями

| Activity | Описание | WF |
|----------|----------|----|
| `TokenObtainPairView` (simplejwt) | username + password → access + refresh токены | **АВТ** |
| `TokenRefreshView` (simplejwt) | refresh → новый access | **АВТ** |
| `LogoutView.post` | Добавить refresh в blacklist | **АВТ** |
| `RegisterView.post` | Валидация данных, хеширование пароля, создание User | **РП** |
| `MeView.get` | Вернуть профиль `request.user` через `UserSerializer` | **АВТ** |

---

## users/serializers.py — валидация и сериализация

| Activity | Описание | WF |
|----------|----------|----|
| `RegisterSerializer.validate` | Проверить совпадение паролей | **РП** |
| `RegisterSerializer.create` | `set_password()`, сохранение User | **РП** |
| `UserSerializer` | Read-only сериализация с `venue_name` | **АВТ**, **РП** |

---

## users/permissions.py — права доступа

| Activity | Описание | WF |
|----------|----------|----|
| `IsEmployee.has_permission` | Любой авторизованный | Все |
| `IsManager.has_permission` | role ∈ {manager, admin} | **РП**, **ГР**, **НЗ**, **ПБ** |
| `IsAdmin.has_permission` | role == admin | Управление venues, users |
| `IsOwnerOrManager.has_object_permission` | Владелец объекта ИЛИ менеджер | **ЗН**, **ПД** |

---

## shifts/services/csv_parser.py — парсинг CSV расписания

| Activity | Описание | WF |
|----------|----------|----|
| `normalize_column_names` | Привести имена колонок к стандарту через `COLUMN_ALIASES` | **ЗГ**, **ГР** |
| `parse_schedule_csv` | CSV → MonthlySchedule + WaiterSlots + ScheduleEntries (в транзакции) | **ЗГ**, **ГР** |
| `_parse_row` | Парсинг одной строки: дата, тип смены, время, часы | **ЗГ**, **ГР** |
| `_parse_time` | Строка → `datetime.time` или `None` | **ЗГ**, **ГР** |

---

## shifts/views.py — расписания и слоты

| Activity | Описание | WF |
|----------|----------|----|
| `UploadScheduleView.post` | Принять CSV файл + venue_id, вызвать `parse_schedule_csv` | **ЗГ** |
| `MonthlyScheduleListView.get_queryset` | Список расписаний (employee — только published своего venue) | — |
| `MonthlyScheduleDetailView.get` | Детали + prefetch слотов и записей | — |
| `PublishScheduleView.post` | draft → published, вызвать `notify_schedule_published` | **ПБ** |
| `DeleteScheduleView.delete` | Удалить черновик (нельзя удалить published) | — |
| `ClaimSlotView.post` | Сотрудник занимает open слот: проверки (venue, статус, дубль) → confirmed, `notify_slot_claimed` | **ЗН** |
| `AssignSlotView.post` | Менеджер назначает: проверки → pending, `notify_manual_assignment` | **НЗ** |
| `UnassignSlotView.post` | Менеджер снимает: → open, обнуление полей | **НЗ** |

---

## shifts/management/commands/send_schedule_reminders.py

| Activity | Описание | WF |
|----------|----------|----|
| `Command.handle` | Проверить: последняя неделя? → для каждого venue без published расписания на следующий месяц → `notify_schedule_reminder` | **НП** |

---

## forecasting/services/ml_runner.py — обёртка ML

| Activity | Описание | WF |
|----------|----------|----|
| `MLRunner.__init__` | Сохранить `cwd` и `sys.path` для восстановления | **МЛ** |
| `MLRunner.execute` | Добавить `ml_data/` в `sys.path`, `chdir`, вызвать `ml_main(**kwargs)`, извлечь метрики, восстановить состояние | **МЛ** |
| `MLRunner._update_status` | Обновить `ForecastRun.status` | **МЛ** |
| `MLRunner._extract_metrics` | Из результата `main()` (dict) или fallback из `.pkl` | **МЛ** |
| `MLRunner._load_metrics_from_model` | `joblib.load(model_orders.pkl)` → извлечь accuracy/mae/r2 с нормализацией имён | **МЛ** |

---

## forecasting/services/forecast_loader.py — CSV → БД

| Activity | Описание | WF |
|----------|----------|----|
| `load_forecast_to_db` | Прочитать `forecast.csv`, удалить старые записи run, `bulk_create` HourlyForecast | **МЛ** |
| `_read_forecast_csv` | Определить delimiter, парсить построчно | **МЛ** |
| `_parse_forecast_row` | Одна строка → dict с типизацией | **МЛ** |

---

## forecasting/services/schedule_generator.py — scheduler → расписание

| Activity | Описание | WF |
|----------|----------|----|
| `run_scheduler` | `chdir(ml_data)`, импорт `scheduler.main()` с fallback на `create_waiter_schedule()`, восстановить `cwd` | **ГР** |
| `load_generated_schedule` | Прочитать `waiter_schedule.csv`, вызвать `parse_schedule_csv` | **ГР** |
| `generate_schedule_full` | `run_scheduler()` → `load_generated_schedule()` → dict с результатами | **ГР** |

---

## forecasting/views.py — API прогнозирования

| Activity | Описание | WF |
|----------|----------|----|
| `RunForecastView.post` | Создать ForecastRun, запустить MLRunner, загрузить прогнозы в БД | **МЛ** |
| `ForecastRunListView.get_queryset` | Список запусков (менеджер — свой venue, admin — все) | — |
| `ForecastRunDetailView.get` | Детали одного запуска | — |
| `HourlyForecastView.get_queryset` | Почасовой прогноз с фильтрами (venue, date_from, date_to, run_id) | — |
| `DailyForecastView.get` | Агрегация по дням: Sum orders, guests; filter morning/evening | — |
| `ModelAccuracyView.get` | Последний run с train_model=True и accuracy_pct | — |
| `GenerateScheduleView.post` | Проверить наличие прогноза → `generate_schedule_full` | **ГР** |
| `UploadRawDataView.post` | Сохранить файл (csv/xlsx/xls) в `ml_data/data/raw/` | **ЗД** |

---

## user_notifications/services.py — создание уведомлений

| Activity | Описание | WF |
|----------|----------|----|
| `notify_schedule_published` | Всем employee venue: «Новое расписание на {месяц}» | **ПБ** |
| `notify_slot_claimed` | Всем manager venue: «{Имя} занял позицию Официант {N}» | **ЗН** |
| `notify_manual_assignment` | Одному employee: «Вас назначили на Официант {N}. Подтвердите.» (requires_confirmation) | **НЗ** |
| `notify_assignment_response` | Всем manager venue: «{Имя} подтвердил/отклонил назначение» | **ПД** |
| `notify_schedule_reminder` | Всем manager venue: «Расписание на {месяц} не опубликовано» | **НП** |

---

## user_notifications/views.py — API уведомлений

| Activity | Описание | WF |
|----------|----------|----|
| `NotificationListView.get_queryset` | Уведомления текущего пользователя (новые первые) | — |
| `UnreadCountView.get` | `count(is_read=False)` | — |
| `MarkReadView.post` | `is_read = True` для одного уведомления | — |
| `MarkAllReadView.post` | `update(is_read=True)` для всех | — |
| `ConfirmAssignmentView.post` | `confirmation_status = accepted`, slot → confirmed, `notify_assignment_response(True)` | **ПД** |
| `RejectAssignmentView.post` | `confirmation_status = rejected`, slot → open, `notify_assignment_response(False)` | **ПД** |

---

## ml_data/main.py — ML-пайплайн

| Activity | Описание | WF |
|----------|----------|----|
| `main(process_data, train_model, make_forecast, evaluate, ...)` | Оркестратор: последовательно вызывает этапы, возвращает dict с метриками | **МЛ** |
| Этап process_data | `process_raw_data()`: Excel/CSV → `processed_orders.csv` | **МЛ** |
| Этап train_model | Обучение XGBoost/RandomForest → `model_orders.pkl` | **МЛ** |
| Этап make_forecast | Генерация почасового прогноза → `forecast.csv` | **МЛ** |
| Этап evaluate | Метрики на тесте: MAE, R², accuracy% | **МЛ** |

---

## ml_data/scheduler.py — генерация расписания

| Activity | Описание | WF |
|----------|----------|----|
| `main(forecast_path, output_path, ...)` | Читает `forecast.csv`, запускает OR-Tools оптимизацию, записывает `waiter_schedule.csv` | **ГР** |
| `create_waiter_schedule(...)` | Fallback: альтернативная точка входа | **ГР** |

---

## Сводная карта: процесс → activities
АВТ Аутентификация
└─ TokenObtainPairView (login)
└─ TokenRefreshView (refresh)
└─ LogoutView.post (blacklist)
└─ MeView.get (профиль)

РП Регистрация персонала
└─ RegisterView.post
└─ RegisterSerializer.validate → .create
└─ IsManager (проверка прав)

ЗД Загрузка данных
└─ UploadRawDataView.post → ml_data/data/raw/

МЛ ML-пайплайн
└─ RunForecastView.post
└─ MLRunner.execute
└─ ml_data.main.main(**kwargs)
└─ process_raw_data (если process_data=True)
└─ train (если train_model=True)
└─ predict (если make_forecast=True)
└─ evaluate (если evaluate=True)
└─ MLRunner._extract_metrics
└─ forecast_loader.load_forecast_to_db → HourlyForecast

ГР Генерация расписания
└─ GenerateScheduleView.post
└─ schedule_generator.run_scheduler
└─ ml_data.scheduler.main()
└─ schedule_generator.load_generated_schedule
└─ csv_parser.parse_schedule_csv → MonthlySchedule (draft)

ЗГ Загрузка CSV (ручная)
└─ UploadScheduleView.post
└─ csv_parser.parse_schedule_csv → MonthlySchedule (draft)

ПБ Публикация расписания
└─ PublishScheduleView.post
└─ notify_schedule_published → Notification (всем employee)

ЗН Занятие позиции
└─ ClaimSlotView.post
└─ проверки: published? venue? open? не занял другой?
└─ slot → confirmed
└─ notify_slot_claimed → Notification (всем manager)

НЗ Ручное назначение
└─ AssignSlotView.post
└─ проверки: open? venue? не назначен?
└─ slot → pending
└─ notify_manual_assignment → Notification (employee, requires_confirmation)

ПД Подтверждение назначения
└─ ConfirmAssignmentView.post
└─ notification → accepted, slot → confirmed
└─ notify_assignment_response(True) → Notification (всем manager)
ИЛИ
└─ RejectAssignmentView.post
└─ notification → rejected, slot → open
└─ notify_assignment_response(False) → Notification (всем manager)

НП Напоминание
└─ send_schedule_reminders (management command)
└─ для каждого venue без published на следующий месяц
└─ notify_schedule_reminder → Notification (всем manager)

---

## Зависимости между модулями
users ──── (нет зависимостей)

shifts/views ──┬─ shifts/services/csv_parser (парсинг CSV)
└─ user_notifications/services (уведомления при publish/claim/assign)

forecasting/views ──┬─ forecasting/services/ml_runner (запуск ML)
├─ forecasting/services/forecast_loader (CSV → БД)
└─ forecasting/services/schedule_generator ──┬─ ml_data/scheduler (OR-Tools)
└─ shifts/services/csv_parser

user_notifications ──── (нет зависимостей от других сервисов)

ml_data ──── (изолирован, вызывается через import)

> Зависимости однонаправленные. `users` и `user_notifications` не знают друг о друге. `ml_data` не знает о Django. Циклических зависимостей нет.