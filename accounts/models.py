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
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    email_verification_code_hash = models.CharField(max_length=64, null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verification_attempts = models.PositiveSmallIntegerField(default=0)
    email_verification_resend_count = models.PositiveIntegerField(default=0)
    email_verification_cooldown_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MAX_EMAIL_VERIFICATION_ATTEMPTS = 5

    def __str__(self):
        return f"{self.user} - {self.role}"
