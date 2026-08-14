"""
signals.py automatically creates a Profile instance whenever a new user is created. 
This is done by listening to the post_save signal of the User model and creating a Profile for the user if it doesn't already exist.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
