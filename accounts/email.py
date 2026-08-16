import json
import logging
import threading
from urllib import request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives


logger = logging.getLogger(__name__)
RESEND_TIMEOUT_SECONDS = 10


def _send_via_resend(*, to_email, subject, text_content, html_content=""):
    api_key = getattr(settings, "RESEND_API_KEY", "")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

    if not api_key:
        raise ImproperlyConfigured("RESEND_API_KEY is required when DEBUG=False.")

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text_content,
    }
    if html_content:
        payload["html"] = html_content

    resend_request = request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with request.urlopen(resend_request, timeout=RESEND_TIMEOUT_SECONDS) as response:
        if response.status not in (200, 201, 202):
            body = response.read(200).decode("utf-8", errors="replace")
            raise RuntimeError(f"Resend API error {response.status}: {body}")


def _send_via_django(*, to_email, subject, text_content, html_content=""):
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )

    if html_content:
        message.attach_alternative(html_content, "text/html")

    message.send(fail_silently=False)


def send_email(*, to_email, subject, text_content, html_content=""):
    if settings.DEBUG:
        _send_via_django(
            to_email=to_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )
    else:
        _send_via_resend(
            to_email=to_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )

    logger.info("Email sent to %s (subject=%s)", to_email, subject)


def send_email_async(*, to_email, subject, text_content, html_content="", context=""):
    def _send():
        try:
            send_email(
                to_email=to_email,
                subject=subject,
                text_content=text_content,
                html_content=html_content,
            )
        except Exception as exc:
            logger.error(
                "Async email delivery failed to %s (context=%s): %s",
                to_email,
                context,
                exc,
            )

    thread = threading.Thread(target=_send, daemon=True, name=f"email-{context}")
    thread.start()


def send_verification_code_email(*, email, code):
    subject, text_content, html_content = build_verification_code_email(code=code)
    send_email(
        to_email=email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )


def send_verification_code_email_async(*, email, code):
    subject, text_content, html_content = build_verification_code_email(code=code)
    send_email_async(
        to_email=email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        context="email_verification",
    )


def build_verification_code_email(*, code):
    subject = "Verify your Event Registration account"
    text_content = f"Your verification code is {code}. It expires in 10 minutes."
    html_content = (
        "<p>Your verification code is:</p>"
        f"<p><strong>{code}</strong></p>"
        "<p>This code expires in 10 minutes.</p>"
    )
    return subject, text_content, html_content
