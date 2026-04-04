from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from users.auth_views import LoginView
from users.views import MeView
from users.urls import user_urlpatterns
from .views import (
    FrontendAppView,
    HealthCheckView,
    AdminOnlySchemaView,
    AdminOnlySwaggerView,
)

urlpatterns = [
    # Auth
    path("api/v1/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("api/v1/auth/", include("users.urls")),

    # Users
    path("api/v1/users/me/", MeView.as_view(), name="user-me"),
    path("api/v1/users/", include(user_urlpatterns)),

    # Shifts + Schedule + Venues
    path("api/v1/", include("shifts.urls")),

    # Forecasting
    path("api/v1/", include("forecasting.urls")),
    
    # Notifications
    path("api/v1/", include("user_notifications.urls")),

    # Health
    path("api/v1/healthz/", HealthCheckView.as_view(), name="healthz"),

    # Frontend SPA (must be last)
    re_path(r"^(?!api/|admin/|static/).*$", FrontendAppView.as_view(), name="frontend-app"),
]

if settings.ENABLE_ADMIN_ROUTES:
    urlpatterns.insert(0, path("admin/", admin.site.urls))

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path("api/v1/schema/", AdminOnlySchemaView.as_view(), name="schema"),
        path("api/v1/docs/", AdminOnlySwaggerView.as_view(url_name="schema"), name="docs"),
    ]
