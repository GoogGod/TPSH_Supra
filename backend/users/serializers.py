from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """
    Создание нового сотрудника.
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "password_confirm",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "venue",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        requester = getattr(request, "user", None)
        role = attrs.get("role", User.Role.EMPLOYEE_NOOB)
        venue = attrs.get("venue")

        if requester and requester.is_authenticated and not requester.is_admin_role:
            if role not in (User.Role.EMPLOYEE_NOOB, User.Role.EMPLOYEE_PRO):
                raise serializers.ValidationError(
                    {"role": "Менеджер может создавать только сотрудников."}
                )

            if not requester.venue_id:
                raise serializers.ValidationError(
                    {"venue": "Менеджер не привязан к объекту."}
                )

            if venue and venue.id != requester.venue_id:
                raise serializers.ValidationError(
                    {"venue": "Можно создавать сотрудников только для своего объекта."}
                )

            attrs["venue"] = requester.venue

        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Пароли не совпадают."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(
        source="venue.name",
        read_only=True,
        default=None,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "venue",
            "venue_name",
            "is_active",
        ]
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "venue",
            "venue_name",
            "is_active",
        ]
        read_only_fields = ["id", "venue_name"]
