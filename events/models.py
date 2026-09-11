from django.db import models
from django.conf import settings

# Create your models here.

class Event(models.Model):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, # Using the custom user model defined in settings.AUTH_USER_MODEL
        on_delete=models.SET_NULL,
        related_name="organized_events",
        null=True,
        blank=True,
    ) 

    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    date_time = models.DateTimeField(db_index=True) # Stores the date and time of the event
    capacity = models.PositiveIntegerField(default=100)
    image_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_time"]

    @property # Allows access to the method as an attribute
    def spots_left(self) -> int:
        active_registrations = self.registrations.filter(is_cancelled=False).count()
        return self.capacity - active_registrations

    @property
    def is_full(self) -> bool:
        return self.spots_left <= 0

    def __str__(self):
        return self.title


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
        return f"{self.user} - {self.event}"


class WaitlistEntry(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PROMOTED = "promoted", "Promoted"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    promoted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=models.Q(status="waiting"),
                name="unique_waiting_user_event",
            ), # Ensures that a user can only have one active waitlist entry for a specific event
        ]
        indexes = [
            models.Index(fields=["event", "status", "created_at"], name="event_waitlist_idx"),
            models.Index(fields=["user", "status"], name="user_waitlist_idx"),
        ] # Indexes for efficient querying of waitlist entries based on event, status, and creation time

    @property
    def position(self) -> int | None:
        if self.status != self.Status.WAITING:
            return None

        return (
            WaitlistEntry.objects.filter(
                event=self.event,
                status=self.Status.WAITING,
                created_at__lte=self.created_at,
            )
            .order_by("created_at", "id")
            .count()
        ) 

    def __str__(self):
        return f"{self.user} - {self.event} ({self.status})"
