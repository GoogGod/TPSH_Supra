from django.urls import path
from .views import RegisterView, LogoutView, UserListView, UserDetailView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]

# Эти подключаются отдельно в core/urls.py
user_urlpatterns = [
    path("", UserListView.as_view(), name="user-list"),
    path("<int:pk>/", UserDetailView.as_view(), name="user-detail"),
]