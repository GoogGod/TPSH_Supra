from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shifts.models import Venue
from users.models import User


class LoginApiTests(APITestCase):
    """12.3 Логин."""

    def setUp(self):
        self.password = "StrongPass123!"
        self.venue = Venue.objects.create(
            name="Ресторан Центральный",
            address="ул. Ленина, 1",
            timezone="Europe/Moscow",
        )
        self.user = User.objects.create_user(
            username="manager_login",
            email="manager_login@example.com",
            password=self.password,
            first_name="Иван",
            last_name="Петров",
            role=User.Role.MANAGER,
            venue=self.venue,
        )

    def test_login_returns_jwt_pair(self):
        response = self.client.post(
            reverse("auth-login"),
            {
                "username": self.user.username,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


class RegisterSecurityTests(APITestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.venue = Venue.objects.create(
            name="Ресторан Центр",
            address="ул. Ленина, 1",
            timezone="Europe/Moscow",
        )
        self.other_venue = Venue.objects.create(
            name="Ресторан Парк",
            address="ул. Парковая, 7",
            timezone="Europe/Moscow",
        )
        self.manager = User.objects.create_user(
            username="manager_register",
            email="manager_register@example.com",
            password=self.password,
            first_name="Мария",
            last_name="Иванова",
            role=User.Role.MANAGER,
            venue=self.venue,
        )
        self.employee = User.objects.create_user(
            username="employee_register",
            email="employee_register@example.com",
            password=self.password,
            first_name="Олег",
            last_name="Смирнов",
            role=User.Role.EMPLOYEE_NOOB,
            venue=self.venue,
        )

    def test_manager_can_register_employee_only_in_own_venue(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "new_employee",
                "email": "new_employee@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "first_name": "Новый",
                "last_name": "Сотрудник",
                "role": User.Role.EMPLOYEE_PRO,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(username="new_employee")
        self.assertEqual(created_user.role, User.Role.EMPLOYEE_PRO)
        self.assertEqual(created_user.venue_id, self.manager.venue_id)

    def test_manager_cannot_register_admin(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "evil_admin",
                "email": "evil_admin@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "first_name": "Злой",
                "last_name": "Админ",
                "role": User.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_manager_cannot_register_employee_for_other_venue(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "cross_venue_user",
                "email": "cross_venue_user@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "first_name": "Чужой",
                "last_name": "Объект",
                "role": User.Role.EMPLOYEE_NOOB,
                "venue": self.other_venue.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("venue", response.data)

    def test_employee_cannot_register_new_users(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "blocked_by_permissions",
                "email": "blocked_by_permissions@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "first_name": "Не",
                "last_name": "Должен",
                "role": User.Role.EMPLOYEE_NOOB,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
