from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Event, Registration


User = get_user_model()


class EventApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        self.token = Token.objects.create(user=self.user)
        self.event = Event.objects.create(
            title="Django Workshop",
            description="Build APIs with Django REST Framework.",
            location="Lagos",
            date_time=timezone.now() + timezone.timedelta(days=7),
            capacity=2,
        )

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_event_list_is_public(self):
        response = self.client.get(reverse("event-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["title"], self.event.title)

    def test_user_can_register_and_receive_token(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_authenticated_user_can_register_for_event(self):
        self.authenticate()

        response = self.client.post(reverse("event-register", args=[self.event.id]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Registration.objects.filter(user=self.user, event=self.event, is_cancelled=False).exists()
        )

    def test_anonymous_user_cannot_register_for_event(self):
        response = self.client.post(reverse("event-register", args=[self.event.id]))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_register_twice_for_same_event(self):
        Registration.objects.create(user=self.user, event=self.event)
        self.authenticate()

        response = self.client.post(reverse("event-register", args=[self.event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Registration.objects.filter(user=self.user, event=self.event, is_cancelled=False).count(),
            1,
        )

    def test_registration_is_rejected_when_event_is_full(self):
        other_user = User.objects.create_user(username="other", password="password123")
        full_event = Event.objects.create(
            title="Small Session",
            description="A small event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        Registration.objects.create(user=other_user, event=full_event)
        self.authenticate()

        response = self.client.post(reverse("event-register", args=[full_event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "No spots left for this event.")

    def test_user_can_view_and_cancel_own_registration(self):
        registration = Registration.objects.create(user=self.user, event=self.event)
        self.authenticate()

        list_response = self.client.get(reverse("my-registrations"))
        cancel_response = self.client.post(reverse("registration-cancel", args=[registration.id]))

        registration.refresh_from_db()
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertTrue(registration.is_cancelled)

    def test_cancelled_registration_can_be_reactivated(self):
        registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            is_cancelled=True,
        )
        self.authenticate()

        response = self.client.post(reverse("event-register", args=[self.event.id]))

        registration.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(registration.is_cancelled)
        self.assertEqual(
            Registration.objects.filter(user=self.user, event=self.event).count(),
            1,
        )

    def test_cancelled_registration_releases_spot(self):
        full_event = Event.objects.create(
            title="One Seat",
            description="A tiny event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=5),
            capacity=1,
        )
        Registration.objects.create(user=self.user, event=full_event, is_cancelled=True)
        self.authenticate()

        response = self.client.post(reverse("event-register", args=[full_event.id]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(full_event.spots_left, 0)
