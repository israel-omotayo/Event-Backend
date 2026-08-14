from django.conf import settings
from django.db import models


class Profile(models.Model):
    class Role(models.TextChoices):
        ATTENDEE = "attendee", "Attendee"
        ORGANIZER = "organizer", "Organizer"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, # Using the custom user model defined in settings.AUTH_USER_MODEL
        on_delete=models.CASCADE,
        related_name="profile",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ATTENDEE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.role}"
