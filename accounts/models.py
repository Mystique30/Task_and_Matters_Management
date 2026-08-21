from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """
    Extends Django's built-in User model with extra fields.
    
    WHY: Django's User model only has username, email, password.
    We need roles (Admin/Manager/Member) for access control.
    
    HOW: OneToOneField links each User to exactly one Profile.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('member', 'Member'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_manager(self):
        return self.role == 'manager'

    @property
    def is_member(self):
        return self.role == 'member'


# --- Django Signals ---
# These run AUTOMATICALLY whenever a User is created/saved.
# This ensures every User always has a Profile.

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """When a new User is created, automatically create their Profile."""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    """When a User is saved, also save their Profile."""
    if hasattr(instance, 'profile'):
        instance.profile.save()
