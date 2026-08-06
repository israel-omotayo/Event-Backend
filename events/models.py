from django.db import models
from django.conf import settings

# Create your models here.

class Event(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    date_time = models.DateTimeField(db_index=True) # Stores the date and time of the event
    capacity = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_time"]

    @property # Allows access to the method as an attribute
    def spots_left(self):
        active_registrations = self.registrations.filter(is_cancelled=False).count()
        return self.capacity - active_registrations

    def __str__(self):
        return self.title # Returns the title of the event when the object is printed or converted to a string


class Registration(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, # Reference to the user model
        on_delete=models.CASCADE,
        related_name="registrations", 
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations",
    ) # Establishes a many-to-one relationship with the Event model

    registered_at = models.DateTimeField(auto_now_add=True)
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                name="unique_user_event_registration",
            ),
        ] # Ensures that a user can only register for a specific event once
        indexes = [
            models.Index(fields=["event", "user"], name="event_user_reg_idx"),
        ]

    def __str__(self):
        return f"{self.user} - {self.event}" # Returns a string representation showing the user and the event they registered for
