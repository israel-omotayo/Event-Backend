from django.urls import path

from .views import (
    CancelWaitlistEntryView,
    CancelRegistrationView,
    EventDetailView,
    EventImageView,
    EventListView,
    EventRegisterView,
    EventWaitlistView,
    MyRegistrationsView,
    MyWaitlistView,
)


urlpatterns = [
    path("events/", EventListView.as_view(), name="event-list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:pk>/image/", EventImageView.as_view(), name="event-image"),
    path("events/<int:pk>/register/", EventRegisterView.as_view(), name="event-register"),
    path("events/<int:pk>/waitlist/", EventWaitlistView.as_view(), name="event-waitlist"),
    path("my-registrations/", MyRegistrationsView.as_view(), name="my-registrations"),
    path("my-waitlist/", MyWaitlistView.as_view(), name="my-waitlist"),
    path("registrations/<int:pk>/cancel/", CancelRegistrationView.as_view(), name="registration-cancel"),
    path("waitlist/<int:pk>/cancel/", CancelWaitlistEntryView.as_view(), name="waitlist-cancel"),
]
