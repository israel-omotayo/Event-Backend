from django.urls import path

from .views import (
    EmailVerificationView,
    EmailTokenObtainPairView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendVerificationCodeView,
    UserRegistrationView,
)
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path("auth/register/", UserRegistrationView.as_view(), name="auth-register"),
    path("auth/verify/", EmailVerificationView.as_view(), name="auth-verify"),
    path("auth/verification/resend/", ResendVerificationCodeView.as_view(), name="auth-verification-resend"),
    path("auth/token/", EmailTokenObtainPairView.as_view(), name="auth-token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/password/reset/request/", PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("auth/password/reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]
