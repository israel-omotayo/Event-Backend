import hashlib
import hmac
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile
from .tasks import send_password_reset_email_task, send_verification_code_email_task


User = get_user_model()


def normalize_email(email):
    return email.strip().lower()


def generate_verification_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_verification_token():
    return secrets.token_urlsafe(32)


def hash_verification_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def hash_verification_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def code_matches(*, code, code_hash):
    return hmac.compare_digest(hash_verification_code(code), code_hash)


def verification_token_matches(*, token, token_hash):
    return hmac.compare_digest(hash_verification_token(token), token_hash)


def encode_user_id(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def decode_user_id(uid):
    try:
        user_id = force_str(urlsafe_base64_decode(uid)) # Decode the base64-encoded user ID and convert it to a string
    except (TypeError, ValueError, OverflowError):
        return None

    return User.objects.filter(pk=user_id).first()


def blacklist_refresh_token(refresh):
    try:
        token = RefreshToken(refresh)
        token.blacklist()
    except TokenError:
        raise serializers.ValidationError({"refresh": "Invalid or expired refresh token."})


def validate_refresh_token_for_user(*, refresh, user):
    try:
        token = RefreshToken(refresh)
    except TokenError:
        raise serializers.ValidationError({"refresh": "Invalid or expired refresh token."})

    if str(token.get("user_id")) != str(user.pk):
        raise serializers.ValidationError({"refresh": "Refresh token does not belong to this user."})

    return token


def blacklist_user_refresh_tokens(user): # Blacklist all refresh tokens for a given user
    for outstanding_token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding_token)


def generate_unique_username_from_email(email):
    base_username = email.split("@", 1)[0].strip() or "user"
    base_username = "".join(
        char if char.isalnum() or char in "._-" else "_" # Replace invalid characters with underscores
        for char in base_username
    )[:120]
    username = base_username
    counter = 1

    while User.objects.filter(username__iexact=username).exists():
        suffix = f"_{counter}"
        username = f"{base_username[:150 - len(suffix)]}{suffix}"
        counter += 1

    return username


def verify_google_id_token(id_token):
    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        raise serializers.ValidationError({"detail": "Google auth is not configured."})

    try:
        return google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            client_id,
        )
    except (ValueError, GoogleAuthError):
        raise serializers.ValidationError({"detail": "Invalid Google token."})


@transaction.atomic
def authenticate_with_google(*, id_token):
    id_info = verify_google_id_token(id_token)
    google_sub = id_info.get("sub")
    email = normalize_email(id_info.get("email", ""))
    email_verified = id_info.get("email_verified")

    if not google_sub or not email:
        raise serializers.ValidationError({"detail": "Invalid Google token."})

    if email_verified is not True:
        raise serializers.ValidationError({"detail": "Google email is not verified."})

    profile = (
        Profile.objects.select_for_update()
        .select_related("user")
        .filter(google_sub=google_sub)
        .first()
    )
    if profile:
        if normalize_email(profile.user.email) != email:
            raise serializers.ValidationError({"detail": "Google account is linked to another email."})

        user = profile.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        return user

    user = User.objects.select_for_update().filter(email__iexact=email).first()
    if user:
        profile = user.profile
        if profile.google_sub and profile.google_sub != google_sub:
            raise serializers.ValidationError({"detail": "This email is linked to another Google account."})
    else:
        user = User.objects.create_user(
            username=generate_unique_username_from_email(email),
            email=email,
            first_name=(id_info.get("given_name") or "").strip(),
            last_name=(id_info.get("family_name") or "").strip(),
            password=None,
            is_active=True,
        )
        profile = user.profile

    fields_to_update = []
    if normalize_email(user.email) != email:
        user.email = email
        fields_to_update.append("email")

    first_name = (id_info.get("given_name") or "").strip()
    last_name = (id_info.get("family_name") or "").strip()
    
    if first_name and not user.first_name:
        user.first_name = first_name
        fields_to_update.append("first_name")
    if last_name and not user.last_name:
        user.last_name = last_name
        fields_to_update.append("last_name")
    if not user.is_active:
        user.is_active = True
        fields_to_update.append("is_active")
    if fields_to_update:
        user.save(update_fields=fields_to_update)

    profile.google_sub = google_sub
    profile.email_verification_code_hash = None
    profile.email_verification_token_hash = None
    profile.email_verification_sent_at = None
    profile.email_verification_attempts = 0
    profile.email_verification_resend_count = 0
    profile.email_verification_cooldown_until = None
    profile.save(
        update_fields=[
            "google_sub",
            "email_verification_code_hash",
            "email_verification_token_hash",
            "email_verification_sent_at",
            "email_verification_attempts",
            "email_verification_resend_count",
            "email_verification_cooldown_until",
            "updated_at",
        ]
    )
    return user


def get_resend_cooldown(resend_count):
    if resend_count <= 3:
        return settings.EMAIL_VERIFICATION_RESEND_COOLDOWN

    minutes = 5 * (2 ** (resend_count - 4))
    cooldown = timezone.timedelta(minutes=minutes)
    return min(cooldown, settings.EMAIL_VERIFICATION_MAX_RESEND_COOLDOWN)


@transaction.atomic
def register_user_with_verification(
    *,
    username,
    email,
    password,
    first_name="",
    last_name="",
):
    email = normalize_email(email)
    username = username.strip()
    first_name = first_name.strip()
    last_name = last_name.strip()

    user_data = {
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password": password,
        "is_active": False,
    }

    existing_user = User.objects.select_for_update().filter(email__iexact=email).first()
    if existing_user:
        if existing_user.is_active:
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )

        profile, _ = Profile.objects.get_or_create(user=existing_user)
        if profile.email_verification_sent_at:
            can_request_at = (
                profile.email_verification_sent_at
                + settings.EMAIL_VERIFICATION_CODE_LIFETIME
            )
            if timezone.now() < can_request_at:
                raise serializers.ValidationError(
                    {"detail": "Please verify your email or wait before requesting a new code."}
                )

        if User.objects.filter(username__iexact=username).exclude(pk=existing_user.pk).exists():
            raise serializers.ValidationError(
                {"username": "A user with this username already exists."}
            )

        existing_user.username = username
        existing_user.first_name = first_name
        existing_user.last_name = last_name
        existing_user.email = email
        existing_user.is_active = False
        existing_user.set_password(password)
        existing_user.save(
            update_fields=[
                "username",
                "first_name",
                "last_name",
                "email",
                "is_active",
                "password",
            ]
        )
        user = existing_user
    else:
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError(
                {"username": "A user with this username already exists."}
            )
        user = User.objects.create_user(**user_data)

    code = generate_verification_code()
    verification_token = generate_verification_token()
    save_verification_code(
        user=user,
        code=code,
        verification_token=verification_token,
    )
    transaction.on_commit(
        lambda: send_verification_code_email_task(email=user.email, code=code)
    )
    return user, verification_token


def save_verification_code(*, user, code, verification_token=None, increment_resend=False):
    profile = user.profile
    profile.email_verification_code_hash = hash_verification_code(code)
    if verification_token is not None:
        profile.email_verification_token_hash = hash_verification_token(verification_token)
    profile.email_verification_sent_at = timezone.now()
    profile.email_verification_attempts = 0

    if increment_resend:
        profile.email_verification_resend_count += 1
        profile.email_verification_cooldown_until = (
            timezone.now() + get_resend_cooldown(profile.email_verification_resend_count)
        )
    else:
        profile.email_verification_resend_count = 0
        profile.email_verification_cooldown_until = None

    profile.save(
        update_fields=[
            "email_verification_code_hash",
            "email_verification_token_hash",
            "email_verification_sent_at",
            "email_verification_attempts",
            "email_verification_resend_count",
            "email_verification_cooldown_until",
            "updated_at",
        ]
    )


def verify_email_code(*, email, code, verification_token):
    validation_error = None

    with transaction.atomic():
        user = (
            User.objects.select_for_update()
            .filter(email__iexact=normalize_email(email))
            .first()
        )

        if not user or user.is_active:
            raise serializers.ValidationError({"detail": "Invalid verification code."})

        profile = user.profile

        if (
            not profile.email_verification_code_hash
            or not profile.email_verification_token_hash
            or not profile.email_verification_sent_at
        ):
            raise serializers.ValidationError({"detail": "Invalid verification code."})

        if not verification_token_matches(
            token=verification_token,
            token_hash=profile.email_verification_token_hash,
        ):
            raise serializers.ValidationError({"detail": "Invalid verification session."})

        if profile.email_verification_attempts >= Profile.MAX_EMAIL_VERIFICATION_ATTEMPTS:
            raise serializers.ValidationError({"detail": "Too many invalid verification attempts."})

        expires_at = profile.email_verification_sent_at + settings.EMAIL_VERIFICATION_CODE_LIFETIME

        if timezone.now() > expires_at:
            raise serializers.ValidationError({"detail": "Verification code has expired."})

        if not code_matches(code=code, code_hash=profile.email_verification_code_hash):
            profile.email_verification_attempts += 1
            profile.save(update_fields=["email_verification_attempts", "updated_at"])
            validation_error = serializers.ValidationError({"detail": "Invalid verification code."})

        else:
            user.is_active = True
            user.save(update_fields=["is_active"])

            profile.email_verification_code_hash = None
            profile.email_verification_token_hash = None
            profile.email_verification_sent_at = None
            profile.email_verification_attempts = 0
            profile.email_verification_resend_count = 0
            profile.email_verification_cooldown_until = None
            profile.save(
                update_fields=[
                    "email_verification_code_hash",
                    "email_verification_token_hash",
                    "email_verification_sent_at",
                    "email_verification_attempts",
                    "email_verification_resend_count",
                    "email_verification_cooldown_until",
                    "updated_at",
                ]
            )

    if validation_error:
        raise validation_error

    return user


@transaction.atomic
def change_user_password(*, user, old_password, new_password, refresh):
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    validate_refresh_token_for_user(refresh=refresh, user=locked_user)

    if not locked_user.check_password(old_password):
        raise serializers.ValidationError({"old_password": "Old password is incorrect."})

    locked_user.set_password(new_password)
    locked_user.save(update_fields=["password"])
    blacklist_user_refresh_tokens(locked_user)
    return locked_user


@transaction.atomic
def request_password_reset(*, email):
    user = (
        User.objects.select_for_update()
        .filter(email__iexact=normalize_email(email), is_active=True)
        .first()
    )

    if not user:
        return False

    uid = encode_user_id(user)
    token = default_token_generator.make_token(user)
    transaction.on_commit(
        lambda: send_password_reset_email_task(
            email=user.email,
            uid=uid,
            token=token,
        )
    )
    return True


@transaction.atomic
def confirm_password_reset(*, uid, token, new_password):
    user = decode_user_id(uid)
    if not user or not user.is_active:
        raise serializers.ValidationError({"detail": "Invalid password reset token."})

    locked_user = User.objects.select_for_update().get(pk=user.pk)
    if not default_token_generator.check_token(locked_user, token):
        raise serializers.ValidationError({"detail": "Invalid password reset token."})

    locked_user.set_password(new_password)
    locked_user.save(update_fields=["password"])
    blacklist_user_refresh_tokens(locked_user)
    return locked_user


@transaction.atomic
def resend_verification_code(*, email, verification_token):
    user = (
        User.objects.select_for_update()
        .filter(email__iexact=normalize_email(email))
        .first()
    )

    if not user or user.is_active:
        raise serializers.ValidationError({"detail": "Invalid verification session."})

    profile = user.profile
    if (
        not profile.email_verification_token_hash
        or not verification_token_matches(
            token=verification_token,
            token_hash=profile.email_verification_token_hash,
        )
    ):
        raise serializers.ValidationError({"detail": "Invalid verification session."})

    if profile.email_verification_cooldown_until:
        if timezone.now() < profile.email_verification_cooldown_until:
            raise serializers.ValidationError(
                {"detail": "Please wait before requesting another verification code."}
            )

    code = generate_verification_code()
    save_verification_code(user=user, code=code, increment_resend=True)
    transaction.on_commit(
        lambda: send_verification_code_email_task(email=user.email, code=code)
    )
    return True
