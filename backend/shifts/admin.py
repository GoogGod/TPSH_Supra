from django.contrib import admin
from .models import Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "timezone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address")
    
# lolkekchebureck