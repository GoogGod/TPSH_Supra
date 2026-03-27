from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from users.views import MeView

urlpatterns = [
    # ── Django Admin ──
    path("admin/", admin.site.urls),

    # ── Аутентификация ──
    path("api/v1/auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("api/v1/auth/", include("users.urls")),  # register, logout

     # ── Пользователи ──
    path("api/v1/users/me/", MeView.as_view(), name="user-me"),
    
    # ── API приложений ──
    path("api/v1/", include("shifts.urls")),  # venues

    # ── Документация API ──
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]