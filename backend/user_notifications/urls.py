from django.urls import path
from .views import (
    NotificationListView,
    UnreadCountView,
    MarkReadView,
    MarkAllReadView,
    ConfirmAssignmentView,
    RejectAssignmentView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/unread-count/", UnreadCountView.as_view(), name="notification-unread"),
    path("notifications/read-all/", MarkAllReadView.as_view(), name="notification-read-all"),
    path("notifications/<int:pk>/read/", MarkReadView.as_view(), name="notification-read"),
    path("notifications/<int:pk>/confirm/", ConfirmAssignmentView.as_view(), name="notification-confirm"),
    path("notifications/<int:pk>/reject/", RejectAssignmentView.as_view(), name="notification-reject"),
]