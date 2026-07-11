from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Event, Registration
from .serializers import EventSerializer, RegistrationSerializer, UserRegistrationSerializer

# Create your views here.

class UserRegistrationView(generics.CreateAPIView):

    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Create a user account",
        responses={201: OpenApiResponse(description="User created with authentication token.")},
    ) # Provides metadata for API documentation, indicating that this endpoint creates a user account and returns a 201 status code with an authentication token upon successful creation

    def create(self, request, *args, **kwargs): # Overrides the default create method to handle user registration and token generation

        serializer = self.get_serializer(data=request.data) # Validates the incoming request data against the UserRegistrationSerializer
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user) # Generates an authentication token for the newly created user, or retrieves an existing token if one already exists
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "token": token.key,
            },
            status=status.HTTP_201_CREATED,
        )


class EventListView(generics.ListAPIView): # Provides a read-only endpoint to list all events
    queryset = Event.objects.all().order_by("date_time") # Retrieves all events from the database and orders them by their date and time in ascending order

    serializer_class = EventSerializer

    permission_classes = [AllowAny]


class EventDetailView(generics.RetrieveAPIView): # Provides a read-only endpoint to retrieve a single event by its primary key (pk)
    queryset = Event.objects.all() # Retrieves all events from the database

    serializer_class = EventSerializer 

    permission_classes = [AllowAny]


class EventRegisterView(APIView): # Provides an endpoint for authenticated users to register for an event

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register for an event",
        request=None,
        responses={
            201: RegistrationSerializer,
            400: OpenApiResponse(description="Already registered or no spots left."),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        }, # extend schema decorator provides metadata for API documentation
    )
    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk) # Retrieves the event with the given primary key (pk) or returns a 404 error if not found

        registration = Registration.objects.filter(
            user=request.user,
            event=event,
        ).first() # Checks if the user is already registered for the event and retrieves the first matching registration if it exists

        if registration and not registration.is_cancelled:
            return Response(
                {"detail": "You are already registered for this event."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event.spots_left <= 0:
            return Response(
                {"detail": "No spots left for this event."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if registration:
            registration.is_cancelled = False
            registration.save(update_fields=["is_cancelled"]) # Updates the existing registration to mark it as not cancelled if the user had previously cancelled their registration

        else:
            registration = Registration.objects.create(user=request.user, event=event)

        serializer = RegistrationSerializer(registration)

        return Response(serializer.data, status=status.HTTP_201_CREATED) # Returns a response with the serialized registration data and the status code indicating that the registration was successfully created


class MyRegistrationsView(generics.ListAPIView): # Provides a read-only endpoint to list all active registrations for the authenticated user

    serializer_class = RegistrationSerializer

    permission_classes = [IsAuthenticated]

    def get_queryset(self): 
        return Registration.objects.filter(
            user=self.request.user,
            is_cancelled=False,
        ).select_related("event") # Retrieves all active registrations for the authenticated user and uses select_related to optimize the database query by fetching related event data in a single query


class CancelRegistrationView(APIView): # Provides an endpoint for authenticated users to cancel their registration for an event

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

        registration.is_cancelled = True
        registration.save(update_fields=["is_cancelled"]) # Updates the registration to mark it as cancelled

        serializer = RegistrationSerializer(registration)
        return Response(serializer.data)
