import hashlib
import hmac
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .email import send_verification_code_email_async
from .models import Profile


User = get_user_model()


def normalize_email(email):
    return email.strip().lower()


def generate_verification_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def code_matches(*, code, code_hash):
    return hmac.compare_digest(hash_verification_code(code), code_hash)


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
    save_verification_code(user=user, code=code)
    transaction.on_commit(
        lambda: send_verification_code_email_async(email=user.email, code=code)
    ) # Send the verification code email after the transaction is committed 
    return user


def save_verification_code(*, user, code, increment_resend=False):
    profile = user.profile
    profile.email_verification_code_hash = hash_verification_code(code)
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
            "email_verification_sent_at",
            "email_verification_attempts",
            "email_verification_resend_count",
            "email_verification_cooldown_until",
            "updated_at",
        ]
    )


def verify_email_code(*, email, code):
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

        if not profile.email_verification_code_hash or not profile.email_verification_sent_at:
            raise serializers.ValidationError({"detail": "Invalid verification code."})

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
            profile.email_verification_sent_at = None
            profile.email_verification_attempts = 0
            profile.email_verification_resend_count = 0
            profile.email_verification_cooldown_until = None
            profile.save(
                update_fields=[
                    "email_verification_code_hash",
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
def resend_verification_code(*, email):
    user = (
        User.objects.select_for_update()
        .filter(email__iexact=normalize_email(email))
        .first()
    )

    if not user or user.is_active:
        return False

    profile = user.profile
    if profile.email_verification_cooldown_until:
        if timezone.now() < profile.email_verification_cooldown_until:
            raise serializers.ValidationError(
                {"detail": "Please wait before requesting another verification code."}
            )

    code = generate_verification_code()
    save_verification_code(user=user, code=code, increment_resend=True)
    transaction.on_commit(
        lambda: send_verification_code_email_async(email=user.email, code=code)
    )
    return True
