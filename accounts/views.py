from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    EmailVerificationSerializer,
    EmailTokenObtainPairSerializer,
    ResendVerificationCodeSerializer,
    UserRegistrationSerializer,
)
from .services import resend_verification_code, verify_email_code


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


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
