from drf_spectacular.utils import OpenApiResponse, extend_schema
from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    EmailVerificationSerializer,
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendVerificationCodeSerializer,
    UserRegistrationSerializer,
)
from .services import (
    blacklist_refresh_token,
    change_user_password,
    confirm_password_reset,
    request_password_reset,
    resend_verification_code,
    verify_email_code,
)


class ProductionScopedThrottleMixin: # A mixin to apply throttling based on the environment
    throttle_classes = [ScopedRateThrottle]

    def get_throttles(self):
        if settings.DEBUG:
            return []
        return super().get_throttles() # 


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Create an unverified user account",
        responses={201: OpenApiResponse(description="Verification code sent.")},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "detail": "Verification code sent to your email.",
            },
            status=status.HTTP_201_CREATED,
        )


class EmailVerificationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify a user email address",
        request=EmailVerificationSerializer,
        responses={200: OpenApiResponse(description="Account verified.")},
    )
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verify_email_code(**serializer.validated_data)
        return Response({"detail": "Account verified. You can now log in."})


class ResendVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Resend an email verification code",
        request=ResendVerificationCodeSerializer,
        responses={200: OpenApiResponse(description="Verification code resent.")},
    )
    def post(self, request):
        serializer = ResendVerificationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resend_verification_code(**serializer.validated_data)
        return Response(
            {"detail": "If an unverified account exists, a new code has been sent."}
        )


class EmailTokenObtainPairView(ProductionScopedThrottleMixin, TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = "auth_login"


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout by blacklisting a refresh token",
        request=LogoutSerializer,
        responses={200: OpenApiResponse(description="Logged out.")},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blacklist_refresh_token(serializer.validated_data["refresh"])
        return Response({"detail": "Logged out successfully."})


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change the authenticated user's password",
        request=PasswordChangeSerializer,
        responses={200: OpenApiResponse(description="Password changed.")},
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        change_user_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
            refresh=serializer.validated_data["refresh"],
        )
        return Response({"detail": "Password changed successfully."})


class PasswordResetRequestView(ProductionScopedThrottleMixin, APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Request a password reset token",
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="Password reset email sent if account exists.")},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(**serializer.validated_data)
        return Response(
            {"detail": "If an account exists for this email, a password reset email has been sent."}
        )


class PasswordResetConfirmView(ProductionScopedThrottleMixin, APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Confirm a password reset token",
        request=PasswordResetConfirmSerializer,
        responses={200: OpenApiResponse(description="Password reset.")},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(
            uid=serializer.validated_data["uid"],
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password reset successfully."})
