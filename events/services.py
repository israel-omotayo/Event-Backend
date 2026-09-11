import logging
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from .models import Event, Registration, WaitlistEntry
from .storage import StorageError, delete_event_image, upload_event_image
from .tasks import (
    send_registration_cancelled_email_task,
    send_registration_confirmed_email_task,
    send_waitlist_cancelled_email_task,
    send_waitlist_joined_email_task,
    send_waitlist_promoted_email_task,
)


logger = logging.getLogger(__name__)
ALLOWED_IMAGE_FORMATS_BY_CONTENT_TYPE = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class RegistrationError(Exception):
    pass


class WaitlistError(Exception):
    pass


class EventImageError(Exception):
    pass


class EventImageStorageError(EventImageError):
    pass


def validate_event_image(file_obj):
    content_type = getattr(file_obj, "content_type", "")
    if content_type not in settings.EVENT_IMAGE_ALLOWED_CONTENT_TYPES:
        raise EventImageError("Upload a JPEG, PNG, or WebP image.")

    if file_obj.size > settings.EVENT_IMAGE_MAX_UPLOAD_SIZE:
        max_size_mb = settings.EVENT_IMAGE_MAX_UPLOAD_SIZE // (1024 * 1024)
        raise EventImageError(f"Image must be {max_size_mb}MB or smaller.")

    try:
        file_obj.seek(0)
        with Image.open(file_obj) as image:
            image.verify()
            image_format = image.format
    except (OSError, UnidentifiedImageError) as exc:
        raise EventImageError("Upload a valid image file.") from exc
    finally:
        file_obj.seek(0)

    expected_format = ALLOWED_IMAGE_FORMATS_BY_CONTENT_TYPE[content_type]
    if image_format != expected_format:
        raise EventImageError("Image file type does not match its content.")


def build_event_image_path(*, event, file_obj):
    extension = settings.EVENT_IMAGE_ALLOWED_CONTENT_TYPES[file_obj.content_type]
    return f"events/{event.pk}/cover/{uuid.uuid4().hex}{extension}"


def delete_event_image_after_commit(path):
    try:
        delete_event_image(path)
    except (ImproperlyConfigured, StorageError):
        logger.exception("Failed to delete old event image from storage: %s", path)


@transaction.atomic
def replace_event_image(*, event, file_obj):
    locked_event = Event.objects.select_for_update().get(pk=event.pk)
    validate_event_image(file_obj)

    old_image_path = locked_event.image_path
    new_image_path = build_event_image_path(event=locked_event, file_obj=file_obj)
    try:
        upload_event_image(
            path=new_image_path,
            file_obj=file_obj,
            content_type=file_obj.content_type,
        )
    except ImproperlyConfigured as exc:
        raise EventImageStorageError("Image storage is not configured.") from exc
    except StorageError as exc:
        raise EventImageStorageError("Image upload failed. Please try again.") from exc

    locked_event.image_path = new_image_path
    locked_event.save(update_fields=["image_path"])

    if old_image_path:
        transaction.on_commit(lambda: delete_event_image_after_commit(old_image_path))

    return locked_event


@transaction.atomic
def remove_event_image(*, event):
    locked_event = Event.objects.select_for_update().get(pk=event.pk)
    old_image_path = locked_event.image_path

    if not old_image_path:
        return locked_event

    locked_event.image_path = ""
    locked_event.save(update_fields=["image_path"])
    transaction.on_commit(lambda: delete_event_image_after_commit(old_image_path))
    return locked_event


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
