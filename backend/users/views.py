from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from .serializers import RegisterSerializer, UserSerializer
from .permissions import IsManager


class RegisterView(APIView):
    """
    Регистрация нового сотрудника.
    Доступно только менеджерам и администраторам.
    """
    permission_classes = [IsAuthenticated, IsManager]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: UserSerializer},
        summary="Зарегистрировать сотрудника",
        tags=["auth"],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Возвращаем через read-сериализатор (с venue_name)
        response_serializer = UserSerializer(user)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """
    Выход из системы.
    Добавляет refresh-токен в чёрный список.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "refresh": {"type": "string"},
                },
                "required": ["refresh"],
            }
        },
        responses={205: None},
        summary="Выйти из аккаунта",
        tags=["auth"],
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Поле 'refresh' обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(
                {"detail": "Невалидный токен."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MeView(APIView):
    """
    Профиль текущего пользователя.
    GET — получить, PATCH — обновить (phone, first_name, last_name).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserSerializer},
        summary="Мой профиль",
        tags=["users"],
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)