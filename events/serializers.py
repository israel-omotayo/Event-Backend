from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Event, Registration

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data) # Create_user method is used to ensure that the password is hashed before being stored

    def validate(self, attrs):
        user = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
        )

        try:
            validate_password(attrs.get("password"), user=user)

        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs



class EventSerializer(serializers.ModelSerializer):
    organizer_username = serializers.CharField(source="organizer.username", read_only=True) # Retrieves the organizer username from the related organizer field in the Event model
    spots_left = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            "id",
            "organizer",
            "organizer_username",
            "title",
            "description",
            "location",
            "date_time",
            "capacity",
            "created_at",
            "spots_left",
        ]
        read_only_fields = ["id", "organizer", "organizer_username", "created_at", "spots_left"]

class RegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = Registration
        fields = ["id", "event", "event_title", "registered_at", "is_cancelled"]
        read_only_fields = ["id", "event_title", "registered_at", "is_cancelled"]
