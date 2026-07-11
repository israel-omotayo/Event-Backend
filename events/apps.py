from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField" # Specifies the default type of primary key field (an auto-incrementing integer field)
    name = 'events'
