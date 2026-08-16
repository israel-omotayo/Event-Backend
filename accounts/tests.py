from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Profile
from .services import get_resend_cooldown, hash_verification_code


User = get_user_model()


@override_settings(DEBUG=True)
class AccountAuthFlowTests(APITestCase):
    def test_registration_creates_inactive_user_and_sends_verification_code(self):
        with (
            patch("accounts.services.generate_verification_code", return_value="123456"),
            patch("accounts.services.send_verification_code_email_async") as send_email_async,
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
        self.assertIsNotNone(user.profile.email_verification_sent_at)
        send_email_async.assert_called_once_with(email="new@example.com", code="123456")

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
            self.client.post(
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
            patch("accounts.services.send_verification_code_email_async") as send_email_async,
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
        send_email_async.assert_called_once_with(email="stale@example.com", code="222222")

    def test_email_verification_activates_user_and_clears_code(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
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
            {"email": "  VERIFY@Example.com  ", "code": "123456"},
            format="json",
        )

        user = User.objects.get(email="verify@example.com")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.profile.email_verification_code_hash)
        self.assertIsNone(user.profile.email_verification_sent_at)
        self.assertEqual(user.profile.email_verification_attempts, 0)

    def test_email_verification_rejects_wrong_code_and_counts_attempt(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
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
            {"email": "wrong@example.com", "code": "654321"},
            format="json",
        )

        user = User.objects.get(email="wrong@example.com")
        user.profile.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.email_verification_attempts, 1)

    def test_email_verification_rejects_expired_code(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
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
            {"email": "expired@example.com", "code": "123456"},
            format="json",
        )

        user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(user.is_active)

    def test_resend_verification_code_replaces_code_and_sets_cooldown(self):
        with patch("accounts.services.generate_verification_code", return_value="123456"):
            self.client.post(
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
            patch("accounts.services.send_verification_code_email_async") as send_email_async,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("auth-verification-resend"),
                    {"email": "  RESEND@Example.com  "},
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
        send_email_async.assert_called_once_with(email="resend@example.com", code="222222")

    def test_resend_verification_code_returns_generic_response_for_unknown_email(self):
        response = self.client.post(
            reverse("auth-verification-resend"),
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "If an unverified account exists, a new code has been sent.",
        )

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
