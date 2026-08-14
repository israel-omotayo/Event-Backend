from datetime import datetime, time

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.permissions import IsOrganizer, IsOrganizerOwner
from .models import Event, Registration
from .serializers import EventSerializer, RegistrationSerializer, UserRegistrationSerializer
from .services import RegistrationError, cancel_registration, register_user_for_event

# Create your views here.


class EventPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

class UserRegistrationView(generics.CreateAPIView):

    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Create a user account",
        responses={201: OpenApiResponse(description="User created with JWT access and refresh tokens.")},
    )


    def create(self, request, *args, **kwargs): # Overrides the default create method to handle user registration and token generation

        serializer = self.get_serializer(data=request.data) # Validates the incoming request data against the UserRegistrationSerializer
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()

        refresh = RefreshToken.for_user(user) # Generates a new refresh token for the newly created user
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


def _parse_datetime_param(value, *, end_of_day=False):
    """
    Parses a date or datetime string into a timezone-aware datetime object.
    """
    if not value: 
        return None 

    parsed = parse_datetime(value) # Attempts to parse the input value as a datetime string using Django's built-in parse_datetime function

    if parsed is None:
        parsed_date = parse_date(value)
        if parsed_date is None:
            return None

        parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone()) # If the parsed datetime does not have timezone information, it is converted to a timezone-aware datetime using the current timezone

    return parsed


class EventListView(generics.ListCreateAPIView):

    serializer_class = EventSerializer

    pagination_class = EventPagination

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return [IsAuthenticated(), IsOrganizer()]

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str, description="Search event title and description."),
            OpenApiParameter("timeframe", str, description="Use 'upcoming' or 'past'."),
            OpenApiParameter("date_from", str, description="Return events on or after this date/datetime."),
            OpenApiParameter("date_to", str, description="Return events on or before this date/datetime."),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Number of events per page, up to 100."),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Event.objects.all().order_by("date_time")
        search = self.request.query_params.get("search", "").strip() 

        timeframe = self.request.query_params.get("timeframe", "").strip().lower()
        date_from = _parse_datetime_param(self.request.query_params.get("date_from"))
        date_to = _parse_datetime_param(
            self.request.query_params.get("date_to"),
            end_of_day=True,
        )

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        if timeframe == "upcoming":
            queryset = queryset.filter(date_time__gte=timezone.now())
        elif timeframe == "past":
            queryset = queryset.filter(date_time__lt=timezone.now())

        if date_from:
            queryset = queryset.filter(date_time__gte=date_from)

        if date_to:
            queryset = queryset.filter(date_time__lte=date_to)

        return queryset

    def perform_create(self, serializer): # Overrides the default perform_create method so as to automacally set the current authenticated user as the organizer
        serializer.save(organizer=self.request.user)


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()

    serializer_class = EventSerializer 

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return [IsAuthenticated(), IsOrganizerOwner()]


class EventRegisterView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register for an event",
        request=None,
        responses={
            201: RegistrationSerializer,
            400: OpenApiResponse(description="Already registered or no spots left."),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
    )
    def post(self, request, pk):
        get_object_or_404(Event, pk=pk) # Retrieves the event with the given primary key (pk) or returns a 404 error if not found
        try:
            registration = register_user_for_event(user=request.user, event_id=pk)

        except RegistrationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            ) # Returns if the user is already registered or if there are no spots left for the event 

        serializer = RegistrationSerializer(registration)

        return Response(serializer.data, status=status.HTTP_201_CREATED) # Returns a response with the serialized registration data and the status code indicating that the registration was successfully created


class MyRegistrationsView(generics.ListAPIView): # Read-only endpoint

    serializer_class = RegistrationSerializer

    permission_classes = [IsAuthenticated]

    def get_queryset(self): 
        return Registration.objects.filter(
            user=self.request.user,
            is_cancelled=False,
        ).select_related("event") # Retrieves all active registrations for the authenticated user and uses select_related to optimize the database query by fetching related event data in a single query


class CancelRegistrationView(APIView):

    permission_classes = [IsAuthenticated] 

    @extend_schema(
        summary="Cancel a registration",
        request=None,
        responses={
            200: RegistrationSerializer,
            401: OpenApiResponse(description="Authentication credentials were not provided."),
            404: OpenApiResponse(description="Registration not found."),
        },
    )# extend schema decorator provides metadata for API documentation
    
    def post(self, request, pk):
        registration = get_object_or_404(
            Registration,
            pk=pk,
            user=request.user,
        ) # Retrieves the registration with the given primary key (pk) for the authenticated user or returns a 404 error if not found

        registration = cancel_registration(registration=registration)

        serializer = RegistrationSerializer(registration)
        return Response(serializer.data)
