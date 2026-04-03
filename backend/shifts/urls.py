from django.urls import path
from .views import (
    VenueListView,
    VenueCreateView,
    UploadScheduleView,
    MonthlyScheduleListView,
    MonthlyScheduleDetailView,
    PublishScheduleView,
    DeleteScheduleView,
    UpdateDraftScheduleEntriesView,
    ClaimSlotView,
    AssignSlotView,
    UnassignSlotView,
    ScheduleStatusView,
    GenerateMonthlyScheduleView,
)

urlpatterns = [
    # Venues
    path("venues/", VenueListView.as_view(), name="venue-list"),
    path("venues/create/", VenueCreateView.as_view(), name="venue-create"),

    # Schedule — статус и генерация
    path("schedule/status/", ScheduleStatusView.as_view(), name="schedule-status"),
    path("schedule/generate/", GenerateMonthlyScheduleView.as_view(), name="schedule-generate"),

    # Schedule — ручная загрузка CSV
    path("schedule/upload/", UploadScheduleView.as_view(), name="schedule-upload"),

    # Schedule — CRUD
    path("schedule/monthly/", MonthlyScheduleListView.as_view(), name="schedule-list"),
    path("schedule/monthly/<int:pk>/", MonthlyScheduleDetailView.as_view(), name="schedule-detail"),
    path(
        "schedule/monthly/<int:pk>/entries/bulk-update/",
        UpdateDraftScheduleEntriesView.as_view(),
        name="schedule-entries-bulk-update",
    ),
    path("schedule/monthly/<int:pk>/publish/", PublishScheduleView.as_view(), name="schedule-publish"),
    path("schedule/monthly/<int:pk>/delete/", DeleteScheduleView.as_view(), name="schedule-delete"),

    # Slots
    path("schedule/slots/<int:pk>/claim/", ClaimSlotView.as_view(), name="slot-claim"),
    path("schedule/slots/<int:pk>/assign/", AssignSlotView.as_view(), name="slot-assign"),
    path("schedule/slots/<int:pk>/unassign/", UnassignSlotView.as_view(), name="slot-unassign"),
]
