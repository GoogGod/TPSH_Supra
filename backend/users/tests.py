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
