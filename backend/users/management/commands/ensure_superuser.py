import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update a superuser from environment variables."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
        first_name = os.getenv("DJANGO_SUPERUSER_FIRST_NAME", "Admin")
        last_name = os.getenv("DJANGO_SUPERUSER_LAST_NAME", "User")

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping superuser creation: set "
                    "DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, "
                    "and DJANGO_SUPERUSER_PASSWORD."
                )
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_staff = True
        user.is_superuser = True

        if hasattr(user, "role"):
            user.role = getattr(User.Role, "ADMIN", "admin")

        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created successfully.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Superuser '{username}' updated successfully.")
        )
