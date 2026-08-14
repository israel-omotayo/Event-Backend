from rest_framework.permissions import BasePermission

from .models import Profile


def user_is_organizer(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_staff:
        return True

    return getattr(getattr(user, "profile", None), "role", None) == Profile.Role.ORGANIZER


class IsOrganizer(BasePermission):
    message = "You must be an organizer to manage events."

    def has_permission(self, request, view):
        return user_is_organizer(request.user)


class IsOrganizerOwner(BasePermission):
    message = "You can only manage events you organize."

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True

        return user_is_organizer(request.user) and obj.organizer_id == request.user.id
