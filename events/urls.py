from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CancelRegistrationView,
    EventDetailView,
    EventListView,
    EventRegisterView,
    MyRegistrationsView,
)


urlpatterns = [
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("events/", EventListView.as_view(), name="event-list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:pk>/register/", EventRegisterView.as_view(), name="event-register"),
    path("my-registrations/", MyRegistrationsView.as_view(), name="my-registrations"),
    path("registrations/<int:pk>/cancel/", CancelRegistrationView.as_view(), name="registration-cancel"),
]
