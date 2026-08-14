from django.apps import AppConfig

# Loads the signals.py when django starts up, ensuring that the signal handlers are registered and ready to respond to events such as user creation.

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from . import signals  # noqa: F401
