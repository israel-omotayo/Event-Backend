from rest_framework import serializers
from django.utils import timezone

from .models import Event, Registration, WaitlistEntry
from .storage import get_public_storage_url


class EventSerializer(serializers.ModelSerializer):
    organizer_username = serializers.CharField(source="organizer.username", read_only=True) # Retrieves the organizer username from the related organizer field in the Event model
    spots_left = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    image_url = serializers.SerializerMethodField()

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
            "image_path",
            "image_url",
            "created_at",
            "spots_left",
            "is_full",
        ]
        read_only_fields = [
            "id",
            "organizer",
            "organizer_username",
            "image_path",
            "image_url",
            "created_at",
            "spots_left",
            "is_full",
        ]

    def get_image_url(self, obj) -> str:
        return get_public_storage_url(obj.image_path)

    def validate_date_time(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Event date and time cannot be in the past.")

        return value


class EventImageUploadSerializer(serializers.Serializer):
    image = serializers.FileField()


class RegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = Registration
        fields = ["id", "event", "event_title", "registered_at", "is_cancelled"]
        read_only_fields = ["id", "event_title", "registered_at", "is_cancelled"]


class RegistrationCancelSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(required=False, default=False)


class WaitlistEntrySerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    position = serializers.ReadOnlyField()

    class Meta:
        model = WaitlistEntry
        fields = ["id", "event", "event_title", "position", "status", "created_at"]
        read_only_fields = ["id", "event", "event_title", "position", "status", "created_at"]
