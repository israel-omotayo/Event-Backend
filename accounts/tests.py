from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Profile
from .services import (
    encode_user_id,
    get_resend_cooldown,
    hash_verification_code,
    hash_verification_token,
)


User = get_user_model()


@override_settings(DEBUG=True)
class AccountAuthFlowTests(APITestCase):
    def test_registration_creates_inactive_user_and_sends_verification_code(self):
        with (
            patch("accounts.services.generate_verification_code", return_value="123456"),
            patch("accounts.services.send_verification_code_email_task") as send_email_task,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("auth-register"),
                    {
                        "username": "newuser",
                        "first_name": "New",
                        "last_name": "User",
                        "email": "new@example.com",
                        "password": "StrongPass123!",
                    },
                    format="json",
                )

        user = User.objects.get(username="newuser")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "Verification code sent to your email.")
        self.assertIn("verification_token", response.data)
        self.assertEqual(response.data["first_name"], "New")
        self.assertEqual(response.data["last_name"], "User")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "User")
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.role, Profile.Role.ATTENDEE)
        self.assertEqual(
            user.profile.email_verification_code_hash,
            hash_verification_code("123456"),
        )
        self.assertEqual(
            user.profile.email_verification_token_hash,
            hash_verification_token(response.data["verification_token"]),
        )
        self.assertIsNotNone(user.profile.email_verification_sent_at)
        send_email_task.assert_called_once_with(email="new@example.com", code="123456")

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user(
            username="existing",
            email="Taken@Example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "newuser",
                "email": "taken@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_registration_strips_and_lowercases_email_before_saving(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "normalized",
                "email": "  MixedCase@Example.COM  ",
                "password": "StrongPass123!",
            },
            format="json",
        )

        user = User.objects.get(username="normalized")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(user.email, "mixedcase@example.com")
        self.assertEqual(response.data["email"], "mixedcase@example.com")

    def test_registration_rejects_duplicate_email_with_surrounding_whitespace(self):
        User.objects.create_user(
            username="existing",
            email="taken@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "newuser",
                "email": "  Taken@Example.com  ",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_registration_blocks_fresh_unverified_duplicate_email(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            register_response = self.client.post(
                reverse("auth-register"),
                {
                    "username": "pending",
                    "email": "pending@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "pending2",
                "email": "pending@example.com",
                "password": "AnotherStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_registration_reuses_stale_unverified_account(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
                reverse("auth-register"),
                {
                    "username": "stale",
                    "email": "stale@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        user = User.objects.get(email="stale@example.com")
        user.profile.email_verification_sent_at = timezone.now() - timezone.timedelta(minutes=11)
        user.profile.save(update_fields=["email_verification_sent_at"])

        with (
            patch("accounts.services.generate_verification_code", return_value="222222"),
            patch("accounts.services.send_verification_code_email_task") as send_email_task,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("auth-register"),
                    {
                        "username": "staleupdated",
                        "first_name": "Stale",
                        "last_name": "Updated",
                        "email": " STALE@Example.com ",
                        "password": "AnotherStrongPass123!",
                    },
                    format="json",
                )

        user.refresh_from_db()
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(email="stale@example.com").count(), 1)
        self.assertEqual(user.username, "staleupdated")
        self.assertEqual(user.first_name, "Stale")
        self.assertEqual(user.last_name, "Updated")
        self.assertFalse(user.is_active)
        self.assertEqual(
            user.profile.email_verification_code_hash,
            hash_verification_code("222222"),
        )
        send_email_task.assert_called_once_with(email="stale@example.com", code="222222")

    def test_email_verification_activates_user_and_clears_code(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            register_response = self.client.post(
                reverse("auth-register"),
                {
                    "username": "verifyme",
                    "email": "verify@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        response = self.client.post(
            reverse("auth-verify"),
            {
                "email": "  VERIFY@Example.com  ",
                "code": "123456",
                "verification_token": register_response.data["verification_token"],
            },
            format="json",
        )

        user = User.objects.get(email="verify@example.com")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.profile.email_verification_code_hash)
        self.assertIsNone(user.profile.email_verification_token_hash)
        self.assertIsNone(user.profile.email_verification_sent_at)
        self.assertEqual(user.profile.email_verification_attempts, 0)

    def test_email_verification_rejects_wrong_code_and_counts_attempt(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            register_response = self.client.post(
                reverse("auth-register"),
                {
                    "username": "wrongcode",
                    "email": "wrong@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        response = self.client.post(
            reverse("auth-verify"),
            {
                "email": "wrong@example.com",
                "code": "654321",
                "verification_token": register_response.data["verification_token"],
            },
            format="json",
        )

        user = User.objects.get(email="wrong@example.com")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.email_verification_attempts, 1)

    def test_email_verification_rejects_expired_code(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            register_response = self.client.post(
                reverse("auth-register"),
                {
                    "username": "expired",
                    "email": "expired@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        user = User.objects.get(email="expired@example.com")
        user.profile.email_verification_sent_at = timezone.now() - timezone.timedelta(minutes=11)
        user.profile.save(update_fields=["email_verification_sent_at"])

        response = self.client.post(
            reverse("auth-verify"),
            {
                "email": "expired@example.com",
                "code": "123456",
                "verification_token": register_response.data["verification_token"],
            },
            format="json",
        )

        user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(user.is_active)

    def test_resend_verification_code_replaces_code_and_sets_cooldown(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            register_response = self.client.post(
                reverse("auth-register"),
                {
                    "username": "resend",
                    "email": "resend@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        with (
            patch("accounts.services.generate_verification_code", return_value="222222"),
            patch("accounts.services.send_verification_code_email_task") as send_email_task,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("auth-verification-resend"),
                    {
                        "email": "  RESEND@Example.com  ",
                        "verification_token": register_response.data["verification_token"],
                    },
                    format="json",
                )

        user = User.objects.get(email="resend@example.com")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            user.profile.email_verification_code_hash,
            hash_verification_code("222222"),
        )
        self.assertEqual(user.profile.email_verification_resend_count, 1)
        self.assertIsNotNone(user.profile.email_verification_cooldown_until)
        send_email_task.assert_called_once_with(email="resend@example.com", code="222222")

    def test_resend_verification_code_rejects_unknown_email_without_pending_session(self):
        response = self.client.post(
            reverse("auth-verification-resend"),
            {
                "email": "missing@example.com",
                "verification_token": "not-a-real-session",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Invalid verification session.")

    def test_resend_verification_code_rejects_wrong_verification_token(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
                reverse("auth-register"),
                {
                    "username": "tokenresend",
                    "email": "tokenresend@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        response = self.client.post(
            reverse("auth-verification-resend"),
            {
                "email": "tokenresend@example.com",
                "verification_token": "wrong-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Invalid verification session.")

    def test_email_verification_rejects_wrong_verification_token(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
                reverse("auth-register"),
                {
                    "username": "tokenverify",
                    "email": "tokenverify@example.com",
                    "password": "StrongPass123!",
                },
                format="json",
            )

        response = self.client.post(
            reverse("auth-verify"),
            {
                "email": "tokenverify@example.com",
                "code": "123456",
                "verification_token": "wrong-token",
            },
            format="json",
        )

        user = User.objects.get(email="tokenverify@example.com")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Invalid verification session.")
        self.assertFalse(user.is_active)

    def test_resend_cooldown_uses_exponential_backoff_after_first_three_resends(self):
        self.assertEqual(get_resend_cooldown(1), timezone.timedelta(minutes=1))
        self.assertEqual(get_resend_cooldown(2), timezone.timedelta(minutes=1))
        self.assertEqual(get_resend_cooldown(3), timezone.timedelta(minutes=1))
        self.assertEqual(get_resend_cooldown(4), timezone.timedelta(minutes=5))
        self.assertEqual(get_resend_cooldown(5), timezone.timedelta(minutes=10))

    def test_verified_user_can_login_with_email_and_password(self):
        user = User.objects.create_user(
            username="loginuser",
            email="Login@Example.com",
            password="StrongPass123!",
            is_active=True,
        )

        response = self.client.post(
            reverse("auth-token"),
            {
                "email": "  login@example.com  ",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn("username", response.data)
        self.assertEqual(User.objects.get(pk=user.pk).email, "Login@example.com")

    def test_login_rejects_username_payload(self):
        User.objects.create_user(
            username="usernamepayload",
            email="usernamepayload@example.com",
            password="StrongPass123!",
            is_active=True,
        )

        response = self.client.post(
            reverse("auth-token"),
            {
                "username": "usernamepayload",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_unverified_user_cannot_login_until_email_is_verified(self):
        User.objects.create_user(
            username="unverifiedlogin",
            email="unverified-login@example.com",
            password="StrongPass123!",
            is_active=False,
        )

        response = self.client.post(
            reverse("auth-token"),
            {
                "email": "unverified-login@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["code"][0]), "account_unverified")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_login_rejects_invalid_email_or_password(self):
        User.objects.create_user(
            username="invalidlogin",
            email="invalid-login@example.com",
            password="StrongPass123!",
            is_active=True,
        )

        response = self.client.post(
            reverse("auth-token"),
            {
                "email": "invalid-login@example.com",
                "password": "WrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertNotIn("access", response.data)

    def test_google_auth_creates_active_user_and_returns_jwt_tokens(self):
        with patch(
            "accounts.services.verify_google_id_token",
            return_value={
                "sub": "google-sub-1",
                "email": "GoogleUser@Example.com",
                "email_verified": True,
                "given_name": "Google",
                "family_name": "User",
            },
        ):
            response = self.client.post(
                reverse("auth-google"),
                {"id_token": "valid-google-token"},
                format="json",
            )

        user = User.objects.get(email="googleuser@example.com")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "googleuser@example.com")
        self.assertTrue(user.is_active)
        self.assertEqual(user.first_name, "Google")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(user.profile.google_sub, "google-sub-1")
        self.assertFalse(user.has_usable_password())

    def test_google_auth_links_existing_inactive_user_by_verified_email(self):
        user = User.objects.create_user(
            username="pendinggoogle",
            email="pending-google@example.com",
            password="OldStrongPass123!",
            is_active=False,
        )
        user.profile.email_verification_code_hash = hash_verification_code("123456")
        user.profile.email_verification_sent_at = timezone.now()
        user.profile.email_verification_attempts = 2
        user.profile.save(
            update_fields=[
                "email_verification_code_hash",
                "email_verification_sent_at",
                "email_verification_attempts",
            ]
        )

        with patch(
            "accounts.services.verify_google_id_token",
            return_value={
                "sub": "google-sub-2",
                "email": "Pending-Google@Example.com",
                "email_verified": True,
                "given_name": "Pending",
                "family_name": "Google",
            },
        ):
            response = self.client.post(
                reverse("auth-google"),
                {"id_token": "valid-google-token"},
                format="json",
            )

        user.refresh_from_db()
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(user.is_active)
        self.assertEqual(user.profile.google_sub, "google-sub-2")
        self.assertIsNone(user.profile.email_verification_code_hash)
        self.assertIsNone(user.profile.email_verification_sent_at)
        self.assertEqual(user.profile.email_verification_attempts, 0)

    def test_google_auth_reuses_existing_google_link(self):
        user = User.objects.create_user(
            username="linkedgoogle",
            email="linked-google@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )
        user.profile.google_sub = "google-sub-3"
        user.profile.save(update_fields=["google_sub"])

        with patch(
            "accounts.services.verify_google_id_token",
            return_value={
                "sub": "google-sub-3",
                "email": "Linked-Google@Example.com",
                "email_verified": True,
            },
        ):
            response = self.client.post(
                reverse("auth-google"),
                {"id_token": "valid-google-token"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["id"], user.id)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_google_auth_rejects_unverified_google_email(self):
        with patch(
            "accounts.services.verify_google_id_token",
            return_value={
                "sub": "google-sub-4",
                "email": "unverified-google@example.com",
                "email_verified": False,
            },
        ):
            response = self.client.post(
                reverse("auth-google"),
                {"id_token": "valid-google-token"},
                format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["detail"][0]), "Google email is not verified.")
        self.assertFalse(User.objects.filter(email="unverified-google@example.com").exists())

    def test_google_auth_rejects_google_sub_linked_to_different_email(self):
        user = User.objects.create_user(
            username="conflictgoogle",
            email="conflict-google@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )
        user.profile.google_sub = "google-sub-5"
        user.profile.save(update_fields=["google_sub"])

        with patch(
            "accounts.services.verify_google_id_token",
            return_value={
                "sub": "google-sub-5",
                "email": "different-google@example.com",
                "email_verified": True,
            },
        ):
            response = self.client.post(
                reverse("auth-google"),
                {"id_token": "valid-google-token"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["detail"][0]), "Google account is linked to another email.")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_google_auth_requires_google_client_id_configuration(self):
        response = self.client.post(
            reverse("auth-google"),
            {"id_token": "valid-google-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["detail"][0]), "Google auth is not configured.")

    def test_logout_blacklists_refresh_token(self):
        User.objects.create_user(
            username="logoutuser",
            email="logout@example.com",
            password="StrongPass123!",
            is_active=True,
        )
        login_response = self.client.post(
            reverse("auth-token"),
            {"email": "logout@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        logout_response = self.client.post(
            reverse("auth-logout"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        self.assertEqual(logout_response.data["detail"], "Logged out successfully.")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_change_updates_password_and_blacklists_refresh_token(self):
        User.objects.create_user(
            username="changeuser",
            email="change@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )
        login_response = self.client.post(
            reverse("auth-token"),
            {"email": "change@example.com", "password": "OldStrongPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        change_response = self.client.post(
            reverse("auth-password-change"),
            {
                "old_password": "OldStrongPass123!",
                "new_password": "NewStrongPass123!",
                "confirm_new_password": "NewStrongPass123!",
                "refresh": login_response.data["refresh"],
            },
            format="json",
        )
        old_login_response = self.client.post(
            reverse("auth-token"),
            {"email": "change@example.com", "password": "OldStrongPass123!"},
            format="json",
        )
        new_login_response = self.client.post(
            reverse("auth-token"),
            {"email": "change@example.com", "password": "NewStrongPass123!"},
            format="json",
        )
        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(change_response.status_code, status.HTTP_200_OK)
        self.assertEqual(change_response.data["detail"], "Password changed successfully.")
        self.assertEqual(old_login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(new_login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_change_rejects_wrong_old_password(self):
        user = User.objects.create_user(
            username="wrongold",
            email="wrongold@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )
        login_response = self.client.post(
            reverse("auth-token"),
            {"email": "wrongold@example.com", "password": "OldStrongPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.post(
            reverse("auth-password-change"),
            {
                "old_password": "WrongOldPass123!",
                "new_password": "NewStrongPass123!",
                "confirm_new_password": "NewStrongPass123!",
                "refresh": login_response.data["refresh"],
            },
            format="json",
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(user.check_password("OldStrongPass123!"))

    def test_password_change_rejects_mismatched_new_passwords(self):
        User.objects.create_user(
            username="mismatch",
            email="mismatch@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )
        login_response = self.client.post(
            reverse("auth-token"),
            {"email": "mismatch@example.com", "password": "OldStrongPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.post(
            reverse("auth-password-change"),
            {
                "old_password": "OldStrongPass123!",
                "new_password": "NewStrongPass123!",
                "confirm_new_password": "DifferentStrongPass123!",
                "refresh": login_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_new_password", response.data)

    def test_password_reset_request_sends_generic_response_and_email_task(self):
        user = User.objects.create_user(
            username="resetuser",
            email="Reset@Example.com",
            password="OldStrongPass123!",
            is_active=True,
        )

        with patch("accounts.services.send_password_reset_email_task") as send_email_task:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("auth-password-reset-request"),
                    {"email": "  reset@example.com  "},
                    format="json",
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "If an account exists for this email, a password reset email has been sent.",
        )
        send_email_task.assert_called_once()
        self.assertEqual(send_email_task.call_args.kwargs["email"], user.email)
        self.assertEqual(send_email_task.call_args.kwargs["uid"], encode_user_id(user))

    def test_password_reset_request_is_generic_for_unknown_email(self):
        with patch("accounts.services.send_password_reset_email_task") as send_email_task:
            response = self.client.post(
                reverse("auth-password-reset-request"),
                {"email": "missing@example.com"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "If an account exists for this email, a password reset email has been sent.",
        )
        send_email_task.assert_not_called()

    def test_password_reset_confirm_updates_password_and_blacklists_refresh_tokens(self):
        user = User.objects.create_user(
            username="confirmreset",
            email="confirm-reset@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )
        login_response = self.client.post(
            reverse("auth-token"),
            {"email": "confirm-reset@example.com", "password": "OldStrongPass123!"},
            format="json",
        )
        uid = encode_user_id(user)
        token = default_token_generator.make_token(user)

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass123!",
                "confirm_new_password": "NewStrongPass123!",
            },
            format="json",
        )
        old_login_response = self.client.post(
            reverse("auth-token"),
            {"email": "confirm-reset@example.com", "password": "OldStrongPass123!"},
            format="json",
        )
        new_login_response = self.client.post(
            reverse("auth-token"),
            {"email": "confirm-reset@example.com", "password": "NewStrongPass123!"},
            format="json",
        )
        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Password reset successfully.")
        self.assertEqual(old_login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(new_login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_confirm_rejects_invalid_token(self):
        user = User.objects.create_user(
            username="badtoken",
            email="badtoken@example.com",
            password="OldStrongPass123!",
            is_active=True,
        )

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": encode_user_id(user),
                "token": "bad-token",
                "new_password": "NewStrongPass123!",
                "confirm_new_password": "NewStrongPass123!",
            },
            format="json",
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(user.check_password("OldStrongPass123!"))
