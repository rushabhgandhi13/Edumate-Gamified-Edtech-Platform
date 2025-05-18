from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, UserProfile
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to create a UserProfile when a new CustomUser is created.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal to save the UserProfile when the CustomUser is saved.
    """
    instance.profile.save() 