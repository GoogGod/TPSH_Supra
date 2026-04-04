# Activities (актуально)

## 1) Полный бизнес-процесс расписания

1. Admin загружает новые сырые данные:
   `POST /api/v1/forecast/upload-data/`
2. Admin (при необходимости) обучает/дообучает модель:
   `POST /api/v1/forecast/run/` с `process_data=true`, `train_model=true`.
3. Manager запрашивает генерацию расписания на месяц:
   `POST /api/v1/schedule/generate/` (`venue`, `year`, `month`).
4. Backend запускает ML + planner и создает `MonthlySchedule` в статусе `draft`.
5. Manager при необходимости правит draft:
   `PATCH /api/v1/schedule/monthly/{id}/entries/bulk-update/`.
6. Manager публикует расписание:
   `POST /api/v1/schedule/monthly/{id}/publish/`.
7. Employee получает опубликованное расписание, может занять свободный слот:
   `POST /api/v1/schedule/slots/{id}/claim/`.

## 2) Что происходит в `/schedule/generate/`

1. Проверка прав (manager/admin) и доступа к venue.
2. Проверка наличия обученной модели (`ForecastRun completed + model_orders.pkl`).
3. Запуск ML прогноза с изоляцией артефактов:
   `ml_data/data/predicted/runs/venue_<venue_id>/run_<forecast_run_id>/`.
4. Загрузка прогноза в БД (`HourlyForecast`).
5. Генерация `waiter_schedule.csv` (main.py + fallback planner при пустом результате).
6. Парсинг schedule CSV в таблицы `MonthlySchedule -> WaiterSlot -> ScheduleEntry`.
7. Возврат ответа 201 + shortage-метрики:
   `available_staff`, `required_waiters_peak`, `lack_staff_peak`, `days_with_shortage`, `shortage_person_days`.

## 3) Роли

- Admin:
  - управление ML (данные/обучение/оценка),
  - создание новых venues,
  - доступ ко всем объектам.
- Manager:
  - генерация и публикация расписания своего venue,
  - редактирование draft,
  - ручные назначения/снятия слотов.
- Employee:
  - просмотр опубликованного расписания своего venue,
  - claim слота,
  - работа с уведомлениями по назначениям.

## 4) Нотификации

- Публикация расписания -> уведомления сотрудникам venue.
- Ручное назначение сотрудника -> уведомление с confirm/reject.
- Ответ сотрудника (confirm/reject) -> уведомление менеджеру.

## 5) SPA + backend

- Backend отдает API на `/api/v1/...`.
- Все не-API маршруты (например `/login`, `/schedule`) отдаются через fallback view для SPA.
