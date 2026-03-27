from users.models import User
from shifts.models import Venue

# ─── Venue ───
venue = Venue.objects.create(
    name="Ресторан Центральный",
    address="ул. Ленина, 1",
    timezone="Europe/Moscow",
)
print(venue)  # Ресторан Центральный

# ─── Admin user ───
admin_user = User.objects.get(username="Immortal")
admin_user.role = User.Role.ADMIN
admin_user.venue = venue
admin_user.save()
print(admin_user)               # "  (Администратор)"
print(admin_user.is_admin_role) # True

# ─── Создать официанта с графиком 4/2, полная смена ───
waiter_1 = User.objects.create_user(
    username="ivanov",
    email="ivanov@supra.local",
    password="testpass123",
    first_name="Иван",
    last_name="Иванов",
    role=User.Role.EMPLOYEE,
    venue=venue,
    schedule_pattern=User.SchedulePattern.FOUR_TWO,
    shift_duration=User.ShiftDuration.FOURTEEN,
)
print(waiter_1)                    # Иванов Иван (Сотрудник)
print(waiter_1.schedule_pattern)   # "4/2"
print(waiter_1.work_days)          # 4
print(waiter_1.off_days)           # 2
print(waiter_1.cycle_length)       # 6
print(waiter_1.shift_duration)     # "14h"

# ─── Официант на вечернюю смену, график 2/2 ───
waiter_2 = User.objects.create_user(
    username="petrov",
    email="petrov@supra.local",
    password="testpass123",
    first_name="Пётр",
    last_name="Петров",
    role=User.Role.EMPLOYEE,
    venue=venue,
    schedule_pattern=User.SchedulePattern.TWO_TWO,
    shift_duration=User.ShiftDuration.EIGHT,
)
print(waiter_2.schedule_pattern)   # "2/2"
print(waiter_2.work_days)          # 2
print(waiter_2.off_days)           # 2
print(waiter_2.cycle_length)       # 4
print(waiter_2.shift_duration)     # "8h"

# ─── Проверка related_name ───
print(venue.staff.count())                              # 3
print(venue.staff.filter(role="employee").count())       # 2

# ─── Фильтрация по графику ───
print(
    venue.staff.filter(schedule_pattern="4/2").count()
)  # 1 (Иванов)

print(
    venue.staff.filter(shift_duration="8h").count()
)  # 1 (Петров)

# ─── Глобальные правила ───
from django.conf import settings
print(settings.SCHEDULE_RULES)
# {'MIN_SHIFTS_PER_WEEK': 4, 'MAX_EVENING_SHIFTS_PER_WEEK': 2, 'SCHEDULE_HORIZON_DAYS': 30}