import logging

from huey.contrib.djhuey import db_task

from .email import (
    send_registration_cancelled_email,
    send_registration_confirmed_email,
    send_waitlist_cancelled_email,
    send_waitlist_joined_email,
    send_waitlist_promoted_email,
)
from .models import Registration, WaitlistEntry


logger = logging.getLogger(__name__)


def _get_registration(registration_id):
    return Registration.objects.select_related("user", "event").get(pk=registration_id)


def _get_waitlist_entry(waitlist_entry_id):
    return WaitlistEntry.objects.select_related("user", "event").get(pk=waitlist_entry_id)


@db_task(retries=3, retry_delay=60)
def send_registration_confirmed_email_task(registration_id):
    try:
        send_registration_confirmed_email(
            registration=_get_registration(registration_id)
        )
    except Registration.DoesNotExist:
        logger.warning(
            "Registration confirmed email skipped; registration %s no longer exists.",
            registration_id,
        )


@db_task(retries=3, retry_delay=60)
def send_registration_cancelled_email_task(registration_id):
    try:
        send_registration_cancelled_email(
            registration=_get_registration(registration_id)
        )
    except Registration.DoesNotExist:
        logger.warning(
            "Registration cancelled email skipped; registration %s no longer exists.",
            registration_id,
        )


@db_task(retries=3, retry_delay=60)
def send_waitlist_joined_email_task(waitlist_entry_id):
    try:
        send_waitlist_joined_email(
            waitlist_entry=_get_waitlist_entry(waitlist_entry_id)
        )
    except WaitlistEntry.DoesNotExist:
        logger.warning(
            "Waitlist joined email skipped; waitlist entry %s no longer exists.",
            waitlist_entry_id,
        )


@db_task(retries=3, retry_delay=60)
def send_waitlist_cancelled_email_task(waitlist_entry_id):
    try:
        send_waitlist_cancelled_email(
            waitlist_entry=_get_waitlist_entry(waitlist_entry_id)
        )
    except WaitlistEntry.DoesNotExist:
        logger.warning(
            "Waitlist cancelled email skipped; waitlist entry %s no longer exists.",
            waitlist_entry_id,
        )


@db_task(retries=3, retry_delay=60)
def send_waitlist_promoted_email_task(registration_id):
    try:
        send_waitlist_promoted_email(
            registration=_get_registration(registration_id)
        )
    except Registration.DoesNotExist:
        logger.warning(
            "Waitlist promoted email skipped; registration %s no longer exists.",
            registration_id,
        )
