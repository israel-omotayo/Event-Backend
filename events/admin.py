from django.contrib import admin
from .models import Event, Registration

# Register your models here.

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "date_time", "capacity", "spots_left")
    search_fields = ("title", "location")
    list_filter = ("date_time",)


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "registered_at", "is_cancelled")
    search_fields = ("user__username", "event__title")
    list_filter = ("is_cancelled", "registered_at")
