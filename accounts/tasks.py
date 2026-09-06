import logging

from huey.contrib.djhuey import task

from .email import send_password_reset_email, send_verification_code_email


logger = logging.getLogger(__name__)


@task(retries=3, retry_delay=60)
def send_verification_code_email_task(*, email, code):
    try:
        send_verification_code_email(email=email, code=code)
    except Exception:
        logger.exception("Verification email task failed for %s", email)
        raise


@task(retries=3, retry_delay=60)
def send_password_reset_email_task(*, email, uid, token):
    try:
        send_password_reset_email(email=email, uid=uid, token=token)
    except Exception:
        logger.exception("Password reset email task failed for %s", email)
        raise
