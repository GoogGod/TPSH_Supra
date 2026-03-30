from django.utils import timezone

from user_notifications.models import Notification
from shifts.models import WaiterSlot, MonthlySchedule


def notify_schedule_published(schedule: MonthlySchedule):
    """
    Уведомить ВСЕХ сотрудников venue: «Вышло новое расписание на {месяц}».
    """
    employees = schedule.venue.staff.filter(
        role__in=["employee_noob", "employee_pro"],
        is_active=True,
    )
    month_label = f"{schedule.month:02d}/{schedule.year}"
    notifications = [
        Notification(
            recipient=emp,
            notification_type=Notification.Type.SCHEDULE_PUBLISHED,
            title="Новое расписание",
            message=f"Опубликовано расписание на {month_label}. Выберите свободную позицию.",
            related_schedule=schedule,
        )
        for emp in employees
    ]
    Notification.objects.bulk_create(notifications)


def notify_slot_claimed(slot: WaiterSlot):
    """
    Уведомить МЕНЕДЖЕРОВ venue: «Иванов И. занял позицию Официант 3».
    """
    managers = slot.schedule.venue.staff.filter(
        role__in=["manager", "admin"],
        is_active=True,
    )
    emp = slot.assigned_employee
    emp_name = emp.get_full_name() or emp.username
    notifications = [
        Notification(
            recipient=mgr,
            notification_type=Notification.Type.SLOT_CLAIMED,
            title="Позиция занята",
            message=f"{emp_name} занял позицию Официант {slot.waiter_num}.",
            related_schedule=slot.schedule,
            related_slot=slot,
        )
        for mgr in managers
    ]
    Notification.objects.bulk_create(notifications)


def notify_manual_assignment(slot: WaiterSlot):
    """
    Уведомить СОТРУДНИКА: «Вас назначили на позицию Официант 3. Подтвердите.»
    Требует подтверждения.
    """
    emp = slot.assigned_employee
    Notification.objects.create(
        recipient=emp,
        notification_type=Notification.Type.MANUAL_ASSIGNMENT,
        title="Назначение на позицию",
        message=(
            f"Вас назначили на позицию Официант {slot.waiter_num}. "
            "Пожалуйста, подтвердите или отклоните назначение."
        ),
        is_read=False,
        requires_confirmation=True,
        confirmation_status=Notification.ConfirmationStatus.PENDING,
        related_schedule=slot.schedule,
        related_slot=slot,
    )


def notify_assignment_response(slot: WaiterSlot, accepted: bool):
    """
    Уведомить МЕНЕДЖЕРОВ venue: «Иванов И. подтвердил/отклонил назначение».
    """
    managers = slot.schedule.venue.staff.filter(
        role__in=["manager", "admin"],
        is_active=True,
    )
    emp = slot.assigned_employee
    emp_name = emp.get_full_name() or emp.username if emp else "Сотрудник"
    action = "подтвердил" if accepted else "отклонил"
    ntype = (
        Notification.Type.ASSIGNMENT_ACCEPTED
        if accepted
        else Notification.Type.ASSIGNMENT_REJECTED
    )

    notifications = [
        Notification(
            recipient=mgr,
            notification_type=ntype,
            title=f"Назначение {action}о",
            message=f"{emp_name} {action} назначение на позицию Официант {slot.waiter_num}.",
            related_schedule=slot.schedule,
            related_slot=slot,
        )
        for mgr in managers
    ]
    Notification.objects.bulk_create(notifications)


def notify_schedule_reminder(schedule_venue, year, month):
    """
    Напоминание менеджерам: «Расписание на {месяц} ещё не готово».
    Вызывается из management-команды.
    """
    managers = schedule_venue.staff.filter(
        role__in=["manager", "admin"],
        is_active=True,
    )
    month_label = f"{month:02d}/{year}"
    notifications = [
        Notification(
            recipient=mgr,
            notification_type=Notification.Type.SCHEDULE_REMINDER,
            title="Напоминание о расписании",
            message=f"Расписание на {month_label} ещё не опубликовано. Осталось мало времени.",
        )
        for mgr in managers
    ]
    Notification.objects.bulk_create(notifications)