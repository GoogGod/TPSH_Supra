from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from .serializers import RegisterSerializer, UserSerializer, UserUpdateSerializer
from .permissions import IsManager
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from django.db import models


class RegisterView(APIView):
    """
    Регистрация нового сотрудника.
    Доступно только менеджерам и администраторам.
    """
    permission_classes = [IsAuthenticated]

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
    
class UserListView(ListAPIView):
    """Список сотрудников объекта. Manager видит свой venue, Admin — всех."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .models import User
        user = self.request.user
        qs = User.objects.select_related("venue").filter(is_active=True)

        if not user.is_admin_role:
            if not user.venue_id:
                qs = qs.filter(role="admin")
            else:
                qs = qs.filter(models.Q(venue=user.venue) | models.Q(role="admin"))

        role = self.request.query_params.get("role")
        venue = self.request.query_params.get("venue")
        search = self.request.query_params.get("search")

        if role:
            qs = qs.filter(role=role)
        if venue:
            qs = qs.filter(venue_id=venue)
        if search:
            qs = qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(username__icontains=search)
            )

        return qs


class UserDetailView(RetrieveUpdateAPIView):
    """Детали / редактирование сотрудника. Admin может менять роль."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        from .models import User
        user = self.request.user
        qs = User.objects.select_related("venue")

        if user.is_manager and not user.is_admin_role:
            qs = qs.filter(venue=user.venue)

        return qs

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UserUpdateSerializer
        return UserSerializer

    def _ensure_admin_for_write(self, request):
        if request.method in ("PATCH", "PUT") and not request.user.is_admin_role:
            return Response(
                {"detail": "Только администратор может изменять данные сотрудника."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def update(self, request, *args, **kwargs):
        denied = self._ensure_admin_for_write(request)
        if denied:
            return denied
        response = super().update(request, *args, **kwargs)
        user = self.get_object()
        response.data = UserSerializer(user).data
        return response

    def partial_update(self, request, *args, **kwargs):
        denied = self._ensure_admin_for_write(request)
        if denied:
            return denied
        response = super().partial_update(request, *args, **kwargs)
        user = self.get_object()
        response.data = UserSerializer(user).data
        return response

    def put(self, request, *args, **kwargs):
        return Response(
            {"detail": "Используйте PATCH для изменения данных сотрудника."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
