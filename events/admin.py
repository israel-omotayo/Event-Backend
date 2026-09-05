from django.contrib import admin
from .models import Event, Registration, WaitlistEntry

# Register your models here.

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "organizer", "location", "date_time", "capacity", "spots_left")
    search_fields = ("title", "location", "organizer__username")
    list_filter = ("date_time",)

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "registered_at", "is_cancelled")
    search_fields = ("user__username", "event__title")
    list_filter = ("is_cancelled", "registered_at")

@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "status", "created_at", "promoted_at")
    search_fields = ("user__username", "event__title")
    list_filter = ("status", "created_at", "promoted_at")
