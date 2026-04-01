"""
Локальный вспомогательный скрипт для ручной проверки моделей.

Важно: не выполнять код на уровне модуля, чтобы `manage.py test`
не падал на импорте `test.py` во время auto-discovery.
"""

from django.conf import settings

from shifts.models import Venue
from users.models import User


def run_demo():
    venue = Venue.objects.create(
        name="Ресторан Центральный",
        address="ул. Ленина, 1",
        timezone="Europe/Moscow",
    )
    print(venue)

    admin_user = User.objects.get(username="Immortal")
    admin_user.role = User.Role.ADMIN
    admin_user.venue = venue
    admin_user.save()
    print(admin_user)
    print(admin_user.is_admin_role)

    waiter_1 = User.objects.create_user(
        username="ivanov",
        email="ivanov@supra.local",
        password="testpass123",
        first_name="Иван",
        last_name="Иванов",
        role=User.Role.EMPLOYEE_NOOB,
        venue=venue,
        schedule_pattern=User.SchedulePattern.FOUR_TWO,
        shift_duration=User.ShiftDuration.FOURTEEN,
    )

    waiter_2 = User.objects.create_user(
        username="petrov",
        email="petrov@supra.local",
        password="testpass123",
        first_name="Пётр",
        last_name="Петров",
        role=User.Role.EMPLOYEE_PRO,
        venue=venue,
        schedule_pattern=User.SchedulePattern.TWO_TWO,
        shift_duration=User.ShiftDuration.EIGHT,
    )

    print(waiter_1.schedule_pattern, waiter_1.work_days, waiter_1.off_days)
    print(waiter_2.schedule_pattern, waiter_2.work_days, waiter_2.off_days)
    print(venue.staff.count())
    print(settings.SCHEDULE_RULES)


if __name__ == "__main__":
    run_demo()
