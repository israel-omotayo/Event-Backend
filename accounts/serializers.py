from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .services import (
    authenticate_with_google,
    decode_user_id,
    normalize_email,
    register_user_with_verification,
)


User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        return normalize_email(value)

    def validate(self, attrs):
        attrs["username"] = attrs.get("username", "").strip()
        attrs["first_name"] = attrs.get("first_name", "").strip()
        attrs["last_name"] = attrs.get("last_name", "").strip()

        existing_email_user = User.objects.filter(email__iexact=attrs["email"]).first()
        if existing_email_user and existing_email_user.is_active:
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )

        username_queryset = User.objects.filter(username__iexact=attrs["username"])
        if existing_email_user:
            username_queryset = username_queryset.exclude(pk=existing_email_user.pk)

        if username_queryset.exists():
            raise serializers.ValidationError({"username": "A user with this username already exists."})

        user = User(
            username=attrs.get("username", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
            email=normalize_email(attrs.get("email", "")),
        )

        try:
            validate_password(attrs.get("password"), user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs

    def create(self, validated_data):
        return register_user_with_verification(**validated_data)


class EmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "Enter a valid 6-digit verification code."},
    )

    def validate_email(self, value):
        return normalize_email(value)


class ResendVerificationCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return normalize_email(value)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)
    refresh = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user

        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )

        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return normalize_email(value)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )

        user = decode_user_id(attrs["uid"])
        if not user:
            raise serializers.ValidationError({"detail": "Invalid password reset token."})

        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        attrs["user"] = authenticate_with_google(id_token=attrs["id_token"])
        return attrs


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("username", None)
        self.fields["email"] = serializers.EmailField(write_only=True)

    def validate(self, attrs):
        email = normalize_email(attrs.get("email", ""))
        password = attrs.get("password", "")
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            User().set_password(password)
            raise serializers.ValidationError(
                {"detail": "Invalid credentials."}
            )

        if not user.check_password(password):
            raise serializers.ValidationError(
                {"detail": "Invalid credentials."}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {
                    "detail": "Account not verified.",
                    "code": "account_unverified",
                }
            )

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
