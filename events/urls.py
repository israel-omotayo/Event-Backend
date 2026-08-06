from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    CancelRegistrationView,
    EventDetailView,
    EventListView,
    EventRegisterView,
    MyRegistrationsView,
    UserRegistrationView,
)


urlpatterns = [
    path("auth/register/", UserRegistrationView.as_view(), name="auth-register"),
    path("auth/token/", obtain_auth_token, name="auth-token"),
    path("events/", EventListView.as_view(), name="event-list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:pk>/register/", EventRegisterView.as_view(), name="event-register"),
    path("my-registrations/", MyRegistrationsView.as_view(), name="my-registrations"),
    path("registrations/<int:pk>/cancel/", CancelRegistrationView.as_view(), name="registration-cancel"),
]
