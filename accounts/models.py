from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models import Sum
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver


class CustomUser(AbstractUser):
    """
    Custom user model with additional fields.
    """
    is_student = models.BooleanField(_('Student Status'), default=False)
    is_instructor = models.BooleanField(_('Instructor Status'), default=False)
    bio = models.TextField(_('Biography'), blank=True)
    profile_picture = models.ImageField(_('Profile Picture'), upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(_('Date of Birth'), blank=True, null=True)
    
    # User preferences
    learning_preference = models.CharField(_('Learning Preference'), max_length=50, blank=True)
    interests = models.TextField(_('Interests'), blank=True)
    
    # Gamification fields
    points = models.PositiveIntegerField(_('Points'), default=0)
    level = models.PositiveIntegerField(_('Level'), default=1)
    streak_days = models.PositiveIntegerField(_('Streak Days'), default=0)
    
    def __str__(self):
        return self.username
    
    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name
    
    @property
    def total_points(self):
        """
        Calculate total points earned by the user.
        """
        from gamification.models import Point
        points = Point.objects.filter(user=self).aggregate(Sum('points'))
        return points['points__sum'] or 0
    
    @property
    def full_name(self):
        return self.get_full_name()
    
    @property
    def badges_count(self):
        return self.badges.count()
    
    @property
    def achievements_count(self):
        return self.achievements.count()
    
    @property
    def courses_count(self):
        return self.courses_enrolled.count()
    
    @property
    def completed_courses_count(self):
        return self.enrollments.filter(status='completed').count()


class UserProfile(models.Model):
    """
    Extended profile information for users.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    location = models.CharField(_('Location'), max_length=100, blank=True)
    website = models.URLField(_('Website'), blank=True)
    social_links = models.JSONField(_('Social Links'), default=dict, blank=True, null=True)
    interests = models.CharField(_('Interests'), max_length=255, blank=True)
    
    # AI personalization preferences
    content_difficulty_preference = models.CharField(
        _('Content Difficulty Preference'),
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('all', 'All Levels')
        ],
        default='all'
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(_('Email Notifications'), default=True)
    achievement_notifications = models.BooleanField(_('Achievement Notifications'), default=True)
    reminder_notifications = models.BooleanField(_('Reminder Notifications'), default=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def get_avatar_url(self):
        # Return a default avatar or user's uploaded avatar
        return "/static/images/default-avatar.png"


class UserActivity(models.Model):
    """
    Track user activities across the platform for analytics and personalization.
    """
    ACTIVITY_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('course_view', 'Course View'),
        ('course_enrollment', 'Course Enrollment'),
        ('module_view', 'Module View'),
        ('lesson_view', 'Lesson View'),
        ('quiz_attempt', 'Quiz Attempt'),
        ('personalized_quiz_attempt', 'Personalized Quiz Attempt'),
        ('achievement_earned', 'Achievement Earned'),
        ('profile_update', 'Profile Update'),
        ('search', 'Search'),
    )
    
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='account_activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Generic foreign key to associate activity with any model
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='account_activities'
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional data about the activity
    data = models.JSONField(default=dict, blank=True, null=True)
    
    class Meta:
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}" 