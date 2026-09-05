from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Profile
from .models import Event, Registration, WaitlistEntry


User = get_user_model()


class EventApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        self.event = Event.objects.create(
            title="Django Workshop",
            description="Build APIs with Django REST Framework.",
            location="Lagos",
            date_time=timezone.now() + timezone.timedelta(days=7),
            capacity=2,
        )

    def authenticate(self):
        token = AccessToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def make_organizer(self, user):
        user.profile.role = Profile.Role.ORGANIZER
        user.profile.save(update_fields=["role"])

    def test_event_list_is_public(self):
        response = self.client.get(reverse("event-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["title"], self.event.title)
        self.assertEqual(response.data["count"], 1)
        self.assertFalse(response.data["results"][0]["is_full"])

    def test_event_list_can_be_paginated(self):
        for index in range(3):
            Event.objects.create(
                title=f"Extra Event {index}",
                description="Another event.",
                location="Online",
                date_time=timezone.now() + timezone.timedelta(days=index + 8),
                capacity=10,
            )

        response = self.client.get(reverse("event-list"), {"page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_event_list_can_search_title_and_description(self):
        Event.objects.create(
            title="Python Meetup",
            description="Async workers and background jobs.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=8),
            capacity=10,
        )
        Event.objects.create(
            title="Frontend Summit",
            description="React and CSS.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=9),
            capacity=10,
        )

        response = self.client.get(reverse("event-list"), {"search": "async"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Python Meetup")

    def test_event_list_can_filter_upcoming_and_past_events(self):
        Event.objects.create(
            title="Past Event",
            description="Already happened.",
            location="Online",
            date_time=timezone.now() - timezone.timedelta(days=2),
            capacity=10,
        )

        upcoming_response = self.client.get(reverse("event-list"), {"timeframe": "upcoming"})
        past_response = self.client.get(reverse("event-list"), {"timeframe": "past"})

        self.assertEqual(upcoming_response.status_code, status.HTTP_200_OK)
        self.assertEqual(past_response.status_code, status.HTTP_200_OK)
        self.assertEqual(upcoming_response.data["count"], 1)
        self.assertEqual(upcoming_response.data["results"][0]["title"], self.event.title)
        self.assertEqual(past_response.data["count"], 1)
        self.assertEqual(past_response.data["results"][0]["title"], "Past Event")

    def test_event_list_can_filter_by_date_range(self):
        in_range = Event.objects.create(
            title="In Range",
            description="Inside requested range.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=14),
            capacity=10,
        )
        Event.objects.create(
            title="Out of Range",
            description="Outside requested range.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=30),
            capacity=10,
        )

        response = self.client.get(
            reverse("event-list"),
            {
                "date_from": (timezone.now() + timezone.timedelta(days=13)).date().isoformat(),
                "date_to": (timezone.now() + timezone.timedelta(days=15)).date().isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], in_range.id)

    def test_new_user_profile_defaults_to_attendee(self):
        new_user = User.objects.create_user(
            username="attendee",
            email="attendee@example.com",
            password="password123",
        )

        self.assertEqual(new_user.profile.role, Profile.Role.ATTENDEE)

    def test_anonymous_user_can_view_event_detail(self):
        response = self.client.get(reverse("event-detail", args=[self.event.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], self.event.title)

    def test_attendee_cannot_create_event(self):
        self.authenticate()

        response = self.client.post(
            reverse("event-list"),
            {
                "title": "Organizer Only",
                "description": "Attendees cannot create this.",
                "location": "Lagos",
                "date_time": (timezone.now() + timezone.timedelta(days=10)).isoformat(),
                "capacity": 20,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_organizer_can_create_event(self):
        self.make_organizer(self.user)
        self.authenticate()

        response = self.client.post(
            reverse("event-list"),
            {
                "title": "Organizer Event",
                "description": "Created through the API.",
                "location": "Lagos",
                "date_time": (timezone.now() + timezone.timedelta(days=10)).isoformat(),
                "capacity": 20,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = Event.objects.get(title="Organizer Event")
        self.assertEqual(event.organizer, self.user)
        self.assertEqual(response.data["organizer"], self.user.id)
        self.assertEqual(response.data["organizer_username"], self.user.username)

    def test_organizer_cannot_create_event_in_the_past(self):
        self.make_organizer(self.user)
        self.authenticate()

        response = self.client.post(
            reverse("event-list"),
            {
                "title": "Past Event",
                "description": "This should not be allowed.",
                "location": "Lagos",
                "date_time": (timezone.now() - timezone.timedelta(days=1)).isoformat(),
                "capacity": 20,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_time", response.data)

    def test_organizer_can_update_own_event(self):
        self.make_organizer(self.user)
        self.event.organizer = self.user
        self.event.save(update_fields=["organizer"])
        self.authenticate()

        response = self.client.patch(
            reverse("event-detail", args=[self.event.id]),
            {"title": "Updated Workshop"},
            format="json",
        )

        self.event.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.event.title, "Updated Workshop")

    def test_organizer_cannot_update_event_date_to_the_past(self):
        self.make_organizer(self.user)
        self.event.organizer = self.user
        self.event.save(update_fields=["organizer"])
        self.authenticate()

        response = self.client.patch(
            reverse("event-detail", args=[self.event.id]),
            {"date_time": (timezone.now() - timezone.timedelta(days=1)).isoformat()},
            format="json",
        )

        self.event.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_time", response.data)
        self.assertGreater(self.event.date_time, timezone.now())

    def test_organizer_can_replace_own_event_with_put(self):
        self.make_organizer(self.user)
        self.event.organizer = self.user
        self.event.save(update_fields=["organizer"])
        self.authenticate()

        response = self.client.put(
            reverse("event-detail", args=[self.event.id]),
            {
                "title": "Full Replace",
                "description": self.event.description,
                "location": self.event.location,
                "date_time": self.event.date_time.isoformat(),
                "capacity": self.event.capacity,
            },
            format="json",
        )

        self.event.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.event.title, "Full Replace")

    def test_organizer_cannot_update_another_organizers_event(self):
        other_user = User.objects.create_user(username="otherorganizer", password="password123")
        self.make_organizer(self.user)
        other_user.profile.role = Profile.Role.ORGANIZER
        other_user.profile.save(update_fields=["role"])
        self.event.organizer = other_user
        self.event.save(update_fields=["organizer"])
        self.authenticate()

        response = self.client.patch(
            reverse("event-detail", args=[self.event.id]),
            {"title": "Hijacked"},
            format="json",
        )

        self.event.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotEqual(self.event.title, "Hijacked")

    @override_settings(DEBUG=True)
    def test_user_registration_requires_email_verification_before_jwt_tokens(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        new_user = User.objects.get(username="newuser")
        self.assertFalse(new_user.is_active)
        self.assertIsNotNone(new_user.profile.email_verification_code_hash)

    def test_registration_rejects_common_password(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "commonuser",
                "email": "common@example.com",
                "password": "password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="commonuser").exists())

    def test_registration_rejects_numeric_password(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "numericuser",
                "email": "numeric@example.com",
                "password": "123456789",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="numericuser").exists())

    def test_registration_rejects_password_similar_to_username(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "janedoe",
                "email": "jane@example.com",
                "password": "janedoe2026",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="janedoe").exists())

    def test_user_can_login_and_refresh_jwt_token(self):
        login_response = self.client.post(
            reverse("auth-token"),
            {
                "email": self.user.email,
                "password": "password123",
            },
            format="json",
        )

        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)
        self.assertIn("refresh", refresh_response.data)

    def test_jwt_settings_are_explicit_and_blacklisting_is_enabled(self):
        self.assertEqual(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"], timezone.timedelta(minutes=60))
        self.assertEqual(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"], timezone.timedelta(days=1))
        self.assertTrue(settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"])
        self.assertIn("rest_framework_simplejwt.token_blacklist", settings.INSTALLED_APPS)

    def test_api_defaults_fail_closed_with_jwt_only(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
            ["rest_framework.permissions.IsAuthenticated"],
        )
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
            ["rest_framework_simplejwt.authentication.JWTAuthentication"],
        )

    def test_schema_and_docs_remain_public(self):
        schema_response = self.client.get(reverse("schema"))
        docs_response = self.client.get(reverse("swagger-ui"))

        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)

    def test_authenticated_user_can_register_for_event(self):
        self.authenticate()

        with patch("events.services.send_registration_confirmed_email_task") as send_email_task:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("event-register", args=[self.event.id]))

        registration = Registration.objects.get(user=self.user, event=self.event, is_cancelled=False)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Registration.objects.filter(user=self.user, event=self.event, is_cancelled=False).exists()
        )
        send_email_task.assert_called_once_with(registration.id)

    def test_authenticated_user_cannot_register_for_past_event(self):
        past_event = Event.objects.create(
            title="Already Done",
            description="This event already happened.",
            location="Online",
            date_time=timezone.now() - timezone.timedelta(days=1),
            capacity=10,
        )
        self.authenticate()

        response = self.client.post(reverse("event-register", args=[past_event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "You cannot register for a past event.",
        )
        self.assertFalse(Registration.objects.filter(user=self.user, event=past_event).exists())

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
        self.assertEqual(response.data["detail"], "Event is full. Join the waitlist instead.")
        self.assertEqual(response.data["code"], "event_full")
        self.assertFalse(WaitlistEntry.objects.filter(user=self.user, event=full_event).exists())

    def test_event_detail_shows_full_event(self):
        other_user = User.objects.create_user(username="fulluser", password="password123")
        full_event = Event.objects.create(
            title="Full Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        Registration.objects.create(user=other_user, event=full_event)

        response = self.client.get(reverse("event-detail", args=[full_event.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["spots_left"], 0)
        self.assertTrue(response.data["is_full"])

    def test_authenticated_user_can_join_waitlist_for_full_event(self):
        other_user = User.objects.create_user(username="registered", password="password123")
        full_event = Event.objects.create(
            title="Waitlist Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        Registration.objects.create(user=other_user, event=full_event)
        self.authenticate()

        with patch("events.services.send_waitlist_joined_email_task") as send_email_task:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("event-waitlist", args=[full_event.id]))

        waitlist_entry = WaitlistEntry.objects.get(user=self.user, event=full_event)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "waitlisted")
        self.assertEqual(response.data["waitlist_entry"]["position"], 1)
        self.assertEqual(waitlist_entry.status, WaitlistEntry.Status.WAITING)
        send_email_task.assert_called_once_with(waitlist_entry.id)

    def test_user_cannot_join_waitlist_twice(self):
        other_user = User.objects.create_user(username="registered", password="password123")
        full_event = Event.objects.create(
            title="Duplicate Waitlist",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        Registration.objects.create(user=other_user, event=full_event)
        WaitlistEntry.objects.create(user=self.user, event=full_event)
        self.authenticate()

        response = self.client.post(reverse("event-waitlist", args=[full_event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "You are already on the waitlist for this event.")
        self.assertEqual(WaitlistEntry.objects.filter(user=self.user, event=full_event).count(), 1)

    def test_user_cannot_join_waitlist_when_event_has_spots(self):
        self.authenticate()

        response = self.client.post(reverse("event-waitlist", args=[self.event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Event still has available spots. Register instead.")

    def test_user_cannot_join_waitlist_when_already_registered(self):
        Registration.objects.create(user=self.user, event=self.event)
        self.authenticate()

        response = self.client.post(reverse("event-waitlist", args=[self.event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "You are already registered for this event.")

    def test_user_cannot_join_waitlist_for_past_event(self):
        past_event = Event.objects.create(
            title="Past Full Session",
            description="Already happened.",
            location="Online",
            date_time=timezone.now() - timezone.timedelta(days=1),
            capacity=0,
        )
        self.authenticate()

        response = self.client.post(reverse("event-waitlist", args=[past_event.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "You cannot join the waitlist for a past event.")

    def test_user_can_view_own_waitlist_entries_with_positions(self):
        other_user = User.objects.create_user(username="registered", password="password123")
        waitlisted_user = User.objects.create_user(username="firstwait", password="password123")
        full_event = Event.objects.create(
            title="My Waitlist Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        Registration.objects.create(user=other_user, event=full_event)
        WaitlistEntry.objects.create(user=waitlisted_user, event=full_event)
        WaitlistEntry.objects.create(user=self.user, event=full_event)
        self.authenticate()

        response = self.client.get(reverse("my-waitlist"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["event_title"], full_event.title)
        self.assertEqual(response.data[0]["position"], 2)

    def test_user_can_cancel_own_waitlist_entry(self):
        full_event = Event.objects.create(
            title="Cancel Waitlist Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        waitlist_entry = WaitlistEntry.objects.create(user=self.user, event=full_event)
        self.authenticate()

        with patch("events.services.send_waitlist_cancelled_email_task") as send_email_task:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("waitlist-cancel", args=[waitlist_entry.id]))

        waitlist_entry.refresh_from_db()
        my_waitlist_response = self.client.get(reverse("my-waitlist"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], WaitlistEntry.Status.CANCELLED)
        self.assertIsNone(response.data["position"])
        self.assertEqual(waitlist_entry.status, WaitlistEntry.Status.CANCELLED)
        self.assertEqual(my_waitlist_response.data, [])
        send_email_task.assert_called_once_with(waitlist_entry.id)

    def test_user_cannot_cancel_promoted_waitlist_entry(self):
        full_event = Event.objects.create(
            title="Promoted Waitlist Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user,
            event=full_event,
            status=WaitlistEntry.Status.PROMOTED,
        )
        self.authenticate()

        response = self.client.post(reverse("waitlist-cancel", args=[waitlist_entry.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Only active waitlist entries can be cancelled.")

    def test_user_cannot_cancel_another_users_waitlist_entry(self):
        other_user = User.objects.create_user(username="otherwait", password="password123")
        full_event = Event.objects.create(
            title="Other Waitlist Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        waitlist_entry = WaitlistEntry.objects.create(user=other_user, event=full_event)
        self.authenticate()

        response = self.client.post(reverse("waitlist-cancel", args=[waitlist_entry.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancelling_registration_promotes_oldest_waitlisted_user(self):
        full_event = Event.objects.create(
            title="Promotion Session",
            description="A full event.",
            location="Online",
            date_time=timezone.now() + timezone.timedelta(days=3),
            capacity=1,
        )
        registration = Registration.objects.create(user=self.user, event=full_event)
        first_waitlisted = User.objects.create_user(username="firstwaitlisted", password="password123")
        second_waitlisted = User.objects.create_user(username="secondwaitlisted", password="password123")
        first_entry = WaitlistEntry.objects.create(user=first_waitlisted, event=full_event)
        second_entry = WaitlistEntry.objects.create(user=second_waitlisted, event=full_event)
        self.authenticate()

        with (
            patch("events.services.send_registration_cancelled_email_task") as send_cancelled_email_task,
            patch("events.services.send_waitlist_promoted_email_task") as send_promoted_email_task,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("registration-cancel", args=[registration.id]),
                    {"confirm": True},
                    format="json",
                )

        registration.refresh_from_db()
        first_entry.refresh_from_db()
        second_entry.refresh_from_db()
        promoted_registration = Registration.objects.get(
            user=first_waitlisted,
            event=full_event,
            is_cancelled=False,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(registration.is_cancelled)
        self.assertTrue(
            Registration.objects.filter(
                user=first_waitlisted,
                event=full_event,
                is_cancelled=False,
            ).exists()
        )
        self.assertEqual(first_entry.status, WaitlistEntry.Status.PROMOTED)
        self.assertIsNotNone(first_entry.promoted_at)
        self.assertEqual(second_entry.status, WaitlistEntry.Status.WAITING)
        self.assertEqual(response.data["promoted_registration"]["id"], promoted_registration.id)
        send_cancelled_email_task.assert_called_once_with(registration.id)
        send_promoted_email_task.assert_called_once_with(promoted_registration.id)

    def test_registration_cancel_requires_confirmation(self):
        registration = Registration.objects.create(user=self.user, event=self.event)
        self.authenticate()

        response = self.client.post(reverse("registration-cancel", args=[registration.id]))

        registration.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Cancelling releases your spot. It will not be reserved for you.",
        )
        self.assertEqual(response.data["code"], "confirmation_required")
        self.assertFalse(registration.is_cancelled)

    def test_user_can_view_and_cancel_own_registration(self):
        registration = Registration.objects.create(user=self.user, event=self.event)
        self.authenticate()

        list_response = self.client.get(reverse("my-registrations"))
        cancel_response = self.client.post(
            reverse("registration-cancel", args=[registration.id]),
            {"confirm": True},
            format="json",
        )

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
