from datetime import date, time

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shifts.models import MonthlySchedule, ScheduleEntry, Venue, WaiterSlot
from shifts.services.csv_parser import parse_schedule_csv
from shifts.views import GenerateMonthlyScheduleView
from user_notifications.models import Notification
from users.models import User


class ShiftsApiTests(APITestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.venue = Venue.objects.create(
            name="Ресторан Центральный",
            address="ул. Ленина, 1",
            timezone="Europe/Moscow",
        )
        self.manager = User.objects.create_user(
            username="manager_slots",
            email="manager_slots@example.com",
            password=self.password,
            first_name="Мария",
            last_name="Иванова",
            role=User.Role.MANAGER,
            venue=self.venue,
        )
        self.employee_pro = User.objects.create_user(
            username="pro_user",
            email="pro_user@example.com",
            password=self.password,
            first_name="Ирина",
            last_name="Петрова",
            role=User.Role.EMPLOYEE_PRO,
            venue=self.venue,
        )
        self.employee_noob = User.objects.create_user(
            username="noob_user",
            email="noob_user@example.com",
            password=self.password,
            first_name="Олег",
            last_name="Смирнов",
            role=User.Role.EMPLOYEE_NOOB,
            venue=self.venue,
        )
        self.admin = User.objects.create_user(
            username="admin_slots",
            email="admin_slots@example.com",
            password=self.password,
            first_name="Анна",
            last_name="Админова",
            role=User.Role.ADMIN,
        )

    def test_schedule_detail_contains_employee_role_flags_from_slot_level(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=4,
            status=MonthlySchedule.Status.DRAFT,
        )

        slot_pro = WaiterSlot.objects.create(
            schedule=schedule,
            waiter_num=1,
            employee_level=WaiterSlot.EmployeeLevel.EMPLOYEE_PRO,
            assigned_employee=self.employee_noob,
            assignment_status=WaiterSlot.AssignmentStatus.CONFIRMED,
        )
        slot_noob = WaiterSlot.objects.create(
            schedule=schedule,
            waiter_num=2,
            employee_level=WaiterSlot.EmployeeLevel.EMPLOYEE_NOOB,
            assigned_employee=self.employee_pro,
            assignment_status=WaiterSlot.AssignmentStatus.PENDING,
        )
        slot_open = WaiterSlot.objects.create(
            schedule=schedule,
            waiter_num=3,
            assignment_status=WaiterSlot.AssignmentStatus.OPEN,
        )

        for slot in (slot_pro, slot_noob, slot_open):
            ScheduleEntry.objects.create(
                slot=slot,
                date=date(2026, 4, 1),
                is_working=False,
                shift_type=ScheduleEntry.ShiftType.OFF,
                waiters_needed=0,
                work_hours=0,
            )

        self.client.force_authenticate(user=self.manager)
        response = self.client.get(reverse("schedule-detail", args=[schedule.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slots = response.data["slots"]
        self.assertEqual(len(slots), 3)

        by_num = {slot["waiter_num"]: slot for slot in slots}
        self.assertEqual(by_num[1]["employee_role"], User.Role.EMPLOYEE_PRO)
        self.assertTrue(by_num[1]["employee_pro"])
        self.assertFalse(by_num[1]["employee_noob"])
        self.assertEqual(by_num[2]["employee_role"], User.Role.EMPLOYEE_NOOB)
        self.assertFalse(by_num[2]["employee_pro"])
        self.assertTrue(by_num[2]["employee_noob"])
        self.assertIsNone(by_num[3]["employee_role"])
        self.assertFalse(by_num[3]["employee_pro"])
        self.assertFalse(by_num[3]["employee_noob"])

    def test_slot_level_is_loaded_from_generated_csv(self):
        csv_content = """date,waiter_id,waiter_num,waiter_type,waiter_type_code,shift_type_code,shift_type,work_start,work_end,work_hours,waiters_needed
2026-04-01,Официант 1,1,Профессионал,1,1,Полная,10.0,22.0,12,4
2026-04-01,Официант 2,2,Новичок,2,2,Утренняя,10.0,16.0,6,4
"""
        schedule = parse_schedule_csv(csv_content, self.venue)

        slot_1 = schedule.slots.get(waiter_num=1)
        slot_2 = schedule.slots.get(waiter_num=2)

        self.assertEqual(slot_1.employee_level, WaiterSlot.EmployeeLevel.EMPLOYEE_PRO)
        self.assertEqual(slot_2.employee_level, WaiterSlot.EmployeeLevel.EMPLOYEE_NOOB)

    def test_slot_level_supports_specialist_novice_and_float_codes(self):
        csv_content = """date,waiter_id,waiter_num,waiter_type,waiter_type_code,waiter_capacity,shift_type_code,shift_type,work_hours,waiters_needed
2026-04-01,Waiter 1,1,specialist,1.0,10,1,full,12,4
2026-04-01,Waiter 2,2,novice,2.0,5,0,off,0,4
"""
        schedule = parse_schedule_csv(csv_content, self.venue)

        slot_1 = schedule.slots.get(waiter_num=1)
        slot_2 = schedule.slots.get(waiter_num=2)

        self.assertEqual(slot_1.employee_level, WaiterSlot.EmployeeLevel.EMPLOYEE_PRO)
        self.assertEqual(slot_2.employee_level, WaiterSlot.EmployeeLevel.EMPLOYEE_NOOB)

    def test_parser_fills_default_shift_times_when_missing(self):
        csv_content = """date,waiter_id,waiter_num,waiter_type,waiter_type_code,shift_type_code,shift_type,work_hours,waiters_needed
2026-04-01,Waiter 1,1,specialist,1.0,2,morning,6,4
2026-04-01,Waiter 2,2,novice,2.0,3,evening,9,4
"""
        schedule = parse_schedule_csv(csv_content, self.venue)

        morning_entry = (
            ScheduleEntry.objects.filter(slot__schedule=schedule, slot__waiter_num=1)
            .order_by("date")
            .first()
        )
        evening_entry = (
            ScheduleEntry.objects.filter(slot__schedule=schedule, slot__waiter_num=2)
            .order_by("date")
            .first()
        )

        self.assertEqual(morning_entry.shift_type, ScheduleEntry.ShiftType.MORNING)
        self.assertEqual(morning_entry.work_start, time(10, 0))
        self.assertEqual(morning_entry.work_end, time(16, 0))

        self.assertEqual(evening_entry.shift_type, ScheduleEntry.ShiftType.EVENING)
        self.assertEqual(evening_entry.work_start, time(16, 0))
        self.assertEqual(evening_entry.work_end, time(1, 0))

    def test_scheduler_profile_does_not_force_ratio_on_single_role(self):
        only_pro_venue = Venue.objects.create(
            name="Only Pro Venue",
            address="Test",
            timezone="Europe/Moscow",
        )
        User.objects.create_user(
            username="only_pro_1",
            email="only_pro_1@example.com",
            password=self.password,
            first_name="Pro",
            last_name="One",
            role=User.Role.EMPLOYEE_PRO,
            venue=only_pro_venue,
        )

        profile = GenerateMonthlyScheduleView._build_scheduler_profile(only_pro_venue)
        self.assertIsNone(profile["noob_ratio"])

    def test_admin_can_create_venue(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("venue-create"),
            {
                "name": "Ресторан Северный",
                "address": "ул. Набережная, 10",
                "timezone": "Europe/Moscow",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Ресторан Северный")
        self.assertTrue(Venue.objects.filter(name="Ресторан Северный").exists())

    def test_manager_can_bulk_update_draft_schedule_entries(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=4,
            status=MonthlySchedule.Status.DRAFT,
        )
        slot = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)
        entry = ScheduleEntry.objects.create(
            slot=slot,
            date=date(2026, 4, 2),
            is_working=False,
            shift_type=ScheduleEntry.ShiftType.OFF,
            waiters_needed=1,
            work_hours=0,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            reverse("schedule-entries-bulk-update", args=[schedule.id]),
            {
                "updates": [
                    {
                        "id": entry.id,
                        "is_working": True,
                        "shift_type": ScheduleEntry.ShiftType.FULL,
                        "waiters_needed": 3,
                        "work_start": "10:00:00",
                        "work_end": "22:00:00",
                        "work_hours": "12.0",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertTrue(entry.is_working)
        self.assertEqual(entry.shift_type, ScheduleEntry.ShiftType.FULL)
        self.assertEqual(entry.waiters_needed, 3)

    def test_manager_can_bulk_update_draft_schedule_entries_with_custom_shift_type(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=4,
            status=MonthlySchedule.Status.DRAFT,
        )
        slot = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)
        entry = ScheduleEntry.objects.create(
            slot=slot,
            date=date(2026, 4, 3),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=1,
            work_start=time(10, 0),
            work_end=time(22, 0),
            work_hours=12,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            reverse("schedule-entries-bulk-update", args=[schedule.id]),
            {
                "updates": [
                    {
                        "id": entry.id,
                        "is_working": True,
                        "shift_type": ScheduleEntry.ShiftType.CUSTOM,
                        "waiters_needed": 2,
                        "work_start": "11:00:00",
                        "work_end": "19:00:00",
                        "work_hours": "8.0",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertEqual(entry.shift_type, ScheduleEntry.ShiftType.CUSTOM)
        self.assertEqual(entry.waiters_needed, 2)

    def test_staff_shortage_metrics_are_calculated(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=4,
            status=MonthlySchedule.Status.DRAFT,
        )
        slot_1 = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)
        slot_2 = WaiterSlot.objects.create(schedule=schedule, waiter_num=2)

        ScheduleEntry.objects.create(
            slot=slot_1,
            date=date(2026, 4, 1),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=4,
            work_hours=12,
        )
        ScheduleEntry.objects.create(
            slot=slot_2,
            date=date(2026, 4, 1),
            is_working=False,
            shift_type=ScheduleEntry.ShiftType.OFF,
            waiters_needed=4,
            work_hours=0,
        )
        ScheduleEntry.objects.create(
            slot=slot_1,
            date=date(2026, 4, 2),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=2,
            work_hours=12,
        )
        ScheduleEntry.objects.create(
            slot=slot_2,
            date=date(2026, 4, 2),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=2,
            work_hours=12,
        )

        metrics = GenerateMonthlyScheduleView._calculate_staff_shortage(schedule)
        self.assertEqual(metrics["available_staff"], 2)
        self.assertEqual(metrics["required_waiters_peak"], 4)
        self.assertEqual(metrics["lack_staff_peak"], 2)
        self.assertEqual(metrics["days_with_shortage"], 1)
        self.assertEqual(metrics["shortage_person_days"], 3)

    def test_unassign_sends_notification_to_employee(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=4,
            status=MonthlySchedule.Status.PUBLISHED,
        )
        slot = WaiterSlot.objects.create(
            schedule=schedule,
            waiter_num=1,
            assigned_employee=self.employee_pro,
            assignment_status=WaiterSlot.AssignmentStatus.CONFIRMED,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(reverse("slot-unassign", args=[slot.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        slot.refresh_from_db()
        self.assertIsNone(slot.assigned_employee)
        self.assertEqual(slot.assignment_status, WaiterSlot.AssignmentStatus.OPEN)

        notification = Notification.objects.filter(
            recipient=self.employee_pro,
            notification_type=Notification.Type.ASSIGNMENT_UNASSIGNED,
            related_slot=slot,
        ).first()
        self.assertIsNotNone(notification)

    def test_manager_can_unpublish_schedule(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=5,
            status=MonthlySchedule.Status.PUBLISHED,
            published_by=self.manager,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(reverse("schedule-unpublish", args=[schedule.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Расписание переведено в черновик.")

        schedule.refresh_from_db()
        self.assertEqual(schedule.status, MonthlySchedule.Status.DRAFT)
        self.assertIsNone(schedule.published_at)
        self.assertIsNone(schedule.published_by)

    def test_manager_can_add_new_slot_to_draft_schedule(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=6,
            status=MonthlySchedule.Status.DRAFT,
        )
        existing_slot = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)
        ScheduleEntry.objects.create(
            slot=existing_slot,
            date=date(2026, 6, 1),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=3,
            work_hours=12,
        )
        ScheduleEntry.objects.create(
            slot=existing_slot,
            date=date(2026, 6, 2),
            is_working=False,
            shift_type=ScheduleEntry.ShiftType.OFF,
            waiters_needed=2,
            work_hours=0,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("schedule-slots-add", args=[schedule.id]),
            {"employee_level": WaiterSlot.EmployeeLevel.EMPLOYEE_PRO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["waiter_num"], 2)
        self.assertEqual(response.data["entries_count"], 2)

        new_slot = WaiterSlot.objects.get(pk=response.data["slot_id"])
        self.assertEqual(new_slot.employee_level, WaiterSlot.EmployeeLevel.EMPLOYEE_PRO)
        new_entries = list(new_slot.entries.order_by("date"))
        self.assertEqual(len(new_entries), 2)
        self.assertTrue(new_entries[0].is_working)
        self.assertEqual(new_entries[0].shift_type, ScheduleEntry.ShiftType.FULL)
        self.assertIsNotNone(new_entries[0].work_start)
        self.assertIsNotNone(new_entries[0].work_end)
        self.assertEqual(new_entries[0].waiters_needed, 3)
        self.assertFalse(new_entries[1].is_working)
        self.assertEqual(new_entries[1].shift_type, ScheduleEntry.ShiftType.OFF)
        self.assertEqual(new_entries[1].waiters_needed, 2)

    def test_manager_cannot_add_slot_to_published_schedule(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=7,
            status=MonthlySchedule.Status.PUBLISHED,
            published_by=self.manager,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(reverse("schedule-slots-add", args=[schedule.id]), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_bulk_update_accepts_empty_time_strings_for_day_off(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=8,
            status=MonthlySchedule.Status.DRAFT,
        )
        slot = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)
        entry = ScheduleEntry.objects.create(
            slot=slot,
            date=date(2026, 8, 10),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=2,
            work_hours=12,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            reverse("schedule-entries-bulk-update", args=[schedule.id]),
            {
                "updates": [
                    {
                        "id": entry.id,
                        "is_working": False,
                        "shift_type": ScheduleEntry.ShiftType.OFF,
                        "waiters_needed": 0,
                        "work_start": "",
                        "work_end": "",
                        "work_hours": 0,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertFalse(entry.is_working)
        self.assertEqual(entry.shift_type, ScheduleEntry.ShiftType.OFF)
        self.assertEqual(entry.waiters_needed, 0)
        self.assertIsNone(entry.work_start)
        self.assertIsNone(entry.work_end)

    def test_manager_can_delete_slot_from_draft_schedule(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=9,
            status=MonthlySchedule.Status.DRAFT,
        )
        slot_1 = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)
        slot_2 = WaiterSlot.objects.create(schedule=schedule, waiter_num=2)
        ScheduleEntry.objects.create(
            slot=slot_1,
            date=date(2026, 9, 1),
            is_working=True,
            shift_type=ScheduleEntry.ShiftType.FULL,
            waiters_needed=2,
            work_hours=12,
        )
        ScheduleEntry.objects.create(
            slot=slot_2,
            date=date(2026, 9, 1),
            is_working=False,
            shift_type=ScheduleEntry.ShiftType.OFF,
            waiters_needed=2,
            work_hours=0,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(
            reverse("schedule-slots-delete", args=[schedule.id, slot_2.id]),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Позиция удалена из черновика.")
        self.assertFalse(WaiterSlot.objects.filter(pk=slot_2.id).exists())
        self.assertFalse(ScheduleEntry.objects.filter(slot_id=slot_2.id).exists())
        self.assertEqual(WaiterSlot.objects.filter(schedule=schedule).count(), 1)

    def test_manager_cannot_delete_slot_from_published_schedule(self):
        schedule = MonthlySchedule.objects.create(
            venue=self.venue,
            year=2026,
            month=10,
            status=MonthlySchedule.Status.PUBLISHED,
            published_by=self.manager,
        )
        slot = WaiterSlot.objects.create(schedule=schedule, waiter_num=1)

        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(
            reverse("schedule-slots-delete", args=[schedule.id, slot.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_manager_cannot_publish_schedule_of_other_venue(self):
        other_venue = Venue.objects.create(
            name="Ресторан Парк",
            address="ул. Парковая, 7",
            timezone="Europe/Moscow",
        )
        other_manager = User.objects.create_user(
            username="manager_other_venue",
            email="manager_other_venue@example.com",
            password=self.password,
            first_name="Другой",
            last_name="Менеджер",
            role=User.Role.MANAGER,
            venue=other_venue,
        )
        foreign_schedule = MonthlySchedule.objects.create(
            venue=other_venue,
            year=2026,
            month=11,
            status=MonthlySchedule.Status.DRAFT,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(reverse("schedule-publish", args=[foreign_schedule.id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # sanity: owner manager can publish
        self.client.force_authenticate(user=other_manager)
        own_response = self.client.post(reverse("schedule-publish", args=[foreign_schedule.id]))
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_unassign_slot_of_other_venue(self):
        other_venue = Venue.objects.create(
            name="Ресторан Восток",
            address="ул. Морская, 3",
            timezone="Europe/Moscow",
        )
        other_employee = User.objects.create_user(
            username="employee_other_venue",
            email="employee_other_venue@example.com",
            password=self.password,
            first_name="Чужой",
            last_name="Сотрудник",
            role=User.Role.EMPLOYEE_PRO,
            venue=other_venue,
        )
        foreign_schedule = MonthlySchedule.objects.create(
            venue=other_venue,
            year=2026,
            month=12,
            status=MonthlySchedule.Status.PUBLISHED,
        )
        foreign_slot = WaiterSlot.objects.create(
            schedule=foreign_schedule,
            waiter_num=1,
            assigned_employee=other_employee,
            assignment_status=WaiterSlot.AssignmentStatus.CONFIRMED,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(reverse("slot-unassign", args=[foreign_slot.id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_read_schedule_status_of_other_venue(self):
        other_venue = Venue.objects.create(
            name="Ресторан Север",
            address="ул. Набережная, 10",
            timezone="Europe/Moscow",
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            reverse("schedule-status"),
            {"venue": other_venue.id, "year": 2026, "month": 4},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
