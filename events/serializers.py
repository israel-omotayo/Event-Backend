from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Event, Registration

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data) # Create_user method is used to ensure that the password is hashed before being stored


class EventSerializer(serializers.ModelSerializer):
    spots_left = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = ["id", "title", "description", "location", "date_time", "capacity", "created_at", "spots_left"]
        read_only_fields = ["id", "created_at", "spots_left"]

class RegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = Registration
        fields = ["id", "event", "event_title", "registered_at", "is_cancelled"]
        read_only_fields = ["id", "event_title", "registered_at", "is_cancelled"]
