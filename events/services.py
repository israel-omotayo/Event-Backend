from django.db import transaction
from django.utils import timezone

from .models import Event, Registration


class RegistrationError(Exception):
    pass


@transaction.atomic
def register_user_for_event(*, user, event_id):
    event = Event.objects.select_for_update().get(pk=event_id)

    registration = (
        Registration.objects.select_for_update()
        .filter(
            user=user,
            event=event,
        )
        .first()
    )

    if registration and not registration.is_cancelled:
        raise RegistrationError("You are already registered for this event.")

    if event.date_time < timezone.now():
        raise RegistrationError("You cannot register for a past event.")

    if event.spots_left <= 0:
        raise RegistrationError("No spots left for this event.")

    if registration:
        registration.is_cancelled = False
        registration.save(update_fields=["is_cancelled"])
        return registration

    return Registration.objects.create(user=user, event=event)


@transaction.atomic
def cancel_registration(*, registration):

    locked_registration = Registration.objects.select_for_update().get(pk=registration.pk) # Lock the registration row to prevent concurrent modifications 
    locked_registration.is_cancelled = True

    locked_registration.save(update_fields=["is_cancelled"])
    return locked_registration
