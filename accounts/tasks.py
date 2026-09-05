import logging

from huey.contrib.djhuey import task

from .email import send_verification_code_email


logger = logging.getLogger(__name__)


@task(retries=3, retry_delay=60)
def send_verification_code_email_task(*, email, code):
    try:
        send_verification_code_email(email=email, code=code)
    except Exception:
        logger.exception("Verification email task failed for %s", email)
        raise
