import logging
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


logger = logging.getLogger(__name__)
SUPABASE_STORAGE_TIMEOUT_SECONDS = 15
SUPABASE_STORAGE_UPLOAD_ATTEMPTS = 2


class StorageError(Exception):
    pass


def _require_supabase_storage_settings():
    if not settings.SUPABASE_URL:
        raise ImproperlyConfigured("SUPABASE_URL is required for Supabase Storage.")

    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise ImproperlyConfigured("SUPABASE_SERVICE_ROLE_KEY is required for Supabase Storage.")


def _headers(*, content_type=None):
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _object_url(path):
    encoded_path = quote(path, safe="/")
    return (
        f"{settings.SUPABASE_URL}/storage/v1/object/"
        f"{settings.SUPABASE_STORAGE_BUCKET}/{encoded_path}"
    )


def get_public_storage_url(path):
    if not path or not settings.SUPABASE_URL:
        return ""

    encoded_path = quote(path, safe="/")
    return (
        f"{settings.SUPABASE_URL}/storage/v1/object/public/"
        f"{settings.SUPABASE_STORAGE_BUCKET}/{encoded_path}"
    )


def upload_event_image(*, path, file_obj, content_type):
    _require_supabase_storage_settings()

    response = None
    for attempt in range(1, SUPABASE_STORAGE_UPLOAD_ATTEMPTS + 1):
        try:
            file_obj.seek(0)
            response = requests.post(
                _object_url(path),
                headers=_headers(content_type=content_type),
                data=file_obj,
                timeout=SUPABASE_STORAGE_TIMEOUT_SECONDS,
            )
            break
        except requests.RequestException as exc:
            logger.warning(
                "Supabase image upload connection failed for %s on attempt %s/%s: %s",
                path,
                attempt,
                SUPABASE_STORAGE_UPLOAD_ATTEMPTS,
                exc,
            )
            if attempt == SUPABASE_STORAGE_UPLOAD_ATTEMPTS:
                raise StorageError("Image upload failed.") from exc

    if response.status_code not in (200, 201):
        response_text = response.text[:300]
        if response.status_code == 400 and "already exists" in response_text.lower():
            return path

        logger.error(
            "Supabase image upload failed for %s: %s %s",
            path,
            response.status_code,
            response_text,
        )
        raise StorageError("Image upload failed.")

    return path


def delete_event_image(path):
    if not path:
        return

    _require_supabase_storage_settings()
    try:
        response = requests.delete(
            f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}",
            headers=_headers(content_type="application/json"),
            json={"prefixes": [path]},
            timeout=SUPABASE_STORAGE_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Supabase image delete connection failed for %s: %s", path, exc)
        raise StorageError("Image delete failed.") from exc
    if response.status_code not in (200, 204):
        logger.warning(
            "Supabase image delete failed for %s: %s %s",
            path,
            response.status_code,
            response.text[:300],
        )
        raise StorageError("Image delete failed.")
