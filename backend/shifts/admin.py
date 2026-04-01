from django.contrib import admin
from .models import Venue, MonthlySchedule, WaiterSlot, ScheduleEntry


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "timezone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address")


class WaiterSlotInline(admin.TabularInline):
    model = WaiterSlot
    extra = 0
    readonly_fields = ("waiter_num", "assigned_employee", "assignment_status")


@admin.register(MonthlySchedule)
class MonthlyScheduleAdmin(admin.ModelAdmin):
    list_display = ("venue", "year", "month", "status", "published_at")
    list_filter = ("status", "venue", "year")
    inlines = [WaiterSlotInline]


class ScheduleEntryInline(admin.TabularInline):
    model = ScheduleEntry
    extra = 0
    readonly_fields = ("date", "shift_type", "work_start", "work_end", "work_hours")


@admin.register(WaiterSlot)
class WaiterSlotAdmin(admin.ModelAdmin):
    list_display = ("schedule", "waiter_num", "assigned_employee", "assignment_status")
    list_filter = ("assignment_status",)
    inlines = [ScheduleEntryInline]
    
# lolkekchebureck