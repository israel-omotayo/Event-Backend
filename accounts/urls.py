from django.urls import path

from .views import (
    EmailVerificationView,
    EmailTokenObtainPairView,
    ResendVerificationCodeView,
    UserRegistrationView,
)


urlpatterns = [
    path("auth/register/", UserRegistrationView.as_view(), name="auth-register"),
    path("auth/verify/", EmailVerificationView.as_view(), name="auth-verify"),
    path("auth/verification/resend/", ResendVerificationCodeView.as_view(), name="auth-verification-resend"),
    path("auth/token/", EmailTokenObtainPairView.as_view(), name="auth-token"),
]
