from django.db import transaction
from django.utils import timezone

from .models import Event, Registration, WaitlistEntry
from .tasks import (
    send_registration_cancelled_email_task,
    send_registration_confirmed_email_task,
    send_waitlist_cancelled_email_task,
    send_waitlist_joined_email_task,
    send_waitlist_promoted_email_task,
)


class RegistrationError(Exception):
    pass


class WaitlistError(Exception):
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
        raise RegistrationError("Event is full. Join the waitlist instead.")

    if registration:
        registration.is_cancelled = False
        registration.save(update_fields=["is_cancelled"])
        transaction.on_commit(
            lambda: send_registration_confirmed_email_task(registration.pk)
        ) # Send the registration confirmed email after the transaction is committed

        return registration

    registration = Registration.objects.create(user=user, event=event)
    transaction.on_commit(
        lambda: send_registration_confirmed_email_task(registration.pk)
    )
    return registration


@transaction.atomic
def cancel_registration(*, registration):

    locked_registration = Registration.objects.select_for_update().get(pk=registration.pk) # Lock the registration row to prevent concurrent modifications 
    locked_registration.is_cancelled = True

    locked_registration.save(update_fields=["is_cancelled"])
    promoted_registration = promote_next_waitlisted_user(event=locked_registration.event)
    transaction.on_commit(
        lambda: send_registration_cancelled_email_task(locked_registration.pk)
    )
    
    if promoted_registration:
        transaction.on_commit(
            lambda: send_waitlist_promoted_email_task(promoted_registration.pk)
        )
    return locked_registration, promoted_registration


@transaction.atomic
def join_event_waitlist(*, user, event_id):
    event = Event.objects.select_for_update().get(pk=event_id)

    if event.date_time < timezone.now():
        raise WaitlistError("You cannot join the waitlist for a past event.")

    registration = (
        Registration.objects.select_for_update()
        .filter(user=user, event=event)
        .first()
    )
    if registration and not registration.is_cancelled:
        raise WaitlistError("You are already registered for this event.")

    if event.spots_left > 0:
        raise WaitlistError("Event still has available spots. Register instead.")

    waitlist_entry, created = WaitlistEntry.objects.get_or_create(
        user=user,
        event=event,
        status=WaitlistEntry.Status.WAITING,
    )
    if not created:
        raise WaitlistError("You are already on the waitlist for this event.")

    transaction.on_commit(
        lambda: send_waitlist_joined_email_task(waitlist_entry.pk)
    )
    return waitlist_entry


@transaction.atomic
def cancel_waitlist_entry(*, waitlist_entry):
    locked_entry = WaitlistEntry.objects.select_for_update().get(pk=waitlist_entry.pk)

    if locked_entry.status != WaitlistEntry.Status.WAITING:
        raise WaitlistError("Only active waitlist entries can be cancelled.")

    locked_entry.status = WaitlistEntry.Status.CANCELLED
    locked_entry.save(update_fields=["status", "updated_at"])
    transaction.on_commit(
        lambda: send_waitlist_cancelled_email_task(locked_entry.pk)
    )
    return locked_entry


def promote_next_waitlisted_user(*, event):
    locked_event = Event.objects.select_for_update().get(pk=event.pk)

    if locked_event.spots_left <= 0:
        return None

    waitlist_entry = (
        WaitlistEntry.objects.select_for_update()
        .filter(event=locked_event, status=WaitlistEntry.Status.WAITING)
        .order_by("created_at", "id")
        .first()
    )
    if not waitlist_entry:
        return None

    registration, _ = Registration.objects.select_for_update().get_or_create(
        user=waitlist_entry.user,
        event=locked_event,
        defaults={"is_cancelled": False},
    )
    if registration.is_cancelled:
        registration.is_cancelled = False
        registration.save(update_fields=["is_cancelled"])

    waitlist_entry.status = WaitlistEntry.Status.PROMOTED
    waitlist_entry.promoted_at = timezone.now()
    waitlist_entry.save(update_fields=["status", "promoted_at", "updated_at"])
    return registration
