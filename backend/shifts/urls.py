from django.urls import path
from .views import (
    VenueListView,
    UploadScheduleView,
    MonthlyScheduleListView,
    MonthlyScheduleDetailView,
    PublishScheduleView,
    DeleteScheduleView,
    ClaimSlotView,
    AssignSlotView,
    UnassignSlotView,
)

urlpatterns = [
    # Venues
    path("venues/", VenueListView.as_view(), name="venue-list"),

    # Schedule
    path("schedule/upload/", UploadScheduleView.as_view(), name="schedule-upload"),
    path("schedule/monthly/", MonthlyScheduleListView.as_view(), name="schedule-list"),
    path("schedule/monthly/<int:pk>/", MonthlyScheduleDetailView.as_view(), name="schedule-detail"),
    path("schedule/monthly/<int:pk>/publish/", PublishScheduleView.as_view(), name="schedule-publish"),
    path("schedule/monthly/<int:pk>/delete/", DeleteScheduleView.as_view(), name="schedule-delete"),

    # Slots
    path("schedule/slots/<int:pk>/claim/", ClaimSlotView.as_view(), name="slot-claim"),
    path("schedule/slots/<int:pk>/assign/", AssignSlotView.as_view(), name="slot-assign"),
    path("schedule/slots/<int:pk>/unassign/", UnassignSlotView.as_view(), name="slot-unassign"),
]