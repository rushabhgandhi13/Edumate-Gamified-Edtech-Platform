from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class UserActivity(models.Model):
    """
    Track user activities for analytics purposes.
    """
    ACTIVITY_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('page_view', 'Page View'),
        ('course_view', 'Course View'),
        ('lesson_view', 'Lesson View'),
        ('quiz_attempt', 'Quiz Attempt'),
        ('search', 'Search'),
        ('download', 'Download'),
        ('comment', 'Comment'),
        ('rating', 'Rating'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analytics_activities'
    )
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    # Generic foreign key to associate activity with any model
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='analytics_activities'
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional data
    session_id = models.CharField(max_length=100, blank=True, null=True)
    referrer = models.URLField(blank=True, null=True)
    
    class Meta:
        verbose_name = _('User Activity')
        verbose_name_plural = _('User Activities')
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class LearningStyle(models.Model):
    """
    Model to store a user's identified learning style and preferences.
    """
    LEARNING_STYLES = (
        ('visual', _('Visual')),
        ('auditory', _('Auditory')),
        ('reading', _('Reading/Writing')),
        ('kinesthetic', _('Kinesthetic')),
        ('multimodal', _('Multimodal')),
    )
    
    PACE_PREFERENCES = (
        ('slow', _('Slow & Thorough')),
        ('moderate', _('Moderate')),
        ('fast', _('Fast-Paced')),
        ('variable', _('Variable')),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_style_profile'
    )
    primary_style = models.CharField(
        max_length=20,
        choices=LEARNING_STYLES,
        default='multimodal'
    )
    secondary_style = models.CharField(
        max_length=20,
        choices=LEARNING_STYLES,
        null=True,
        blank=True
    )
    pace_preference = models.CharField(
        max_length=20,
        choices=PACE_PREFERENCES,
        default='moderate'
    )
    prefers_group_learning = models.BooleanField(default=True)
    prefers_practical_examples = models.BooleanField(default=True)
    prefers_theory_first = models.BooleanField(default=False)
    attention_span_minutes = models.PositiveIntegerField(default=30)
    confidence_level = models.IntegerField(
        default=3,
        choices=[(1, _('Very Low')), (2, _('Low')), (3, _('Moderate')), 
                 (4, _('High')), (5, _('Very High'))]
    )
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Learning Style')
        verbose_name_plural = _('Learning Styles')
    
    def __str__(self):
        return f"{self.user.username}'s Learning Style: {self.get_primary_style_display()}"


class LearningInsight(models.Model):
    """
    AI-generated insights about user learning patterns.
    """
    INSIGHT_TYPES = (
        ('learning_pattern', 'Learning Pattern'),
        ('engagement', 'Engagement'),
        ('performance', 'Performance'),
        ('recommendation', 'Recommendation'),
        ('study_habit', 'Study Habit'),
        ('strength', 'Strength'),
        ('weakness', 'Weakness'),
        ('learning_style', 'Learning Style'),
        ('improvement', 'Improvement Area'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_insights')
    title = models.CharField(max_length=255, default="Learning Insight")
    description = models.TextField(blank=True, default="No description provided")
    insight_type = models.CharField(max_length=50, choices=INSIGHT_TYPES)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    relevance_score = models.FloatField(default=0.5, help_text=_("How relevant this insight is to the user (0-1)"))
    
    class Meta:
        verbose_name = _('Learning Insight')
        verbose_name_plural = _('Learning Insights')
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class AILearningRecommendation(models.Model):
    """
    AI-generated personalized learning recommendations for users.
    """
    RECOMMENDATION_TYPES = (
        ('course', _('Course Recommendation')),
        ('resource', _('Learning Resource')),
        ('study_technique', _('Study Technique')),
        ('content_format', _('Content Format')),
        ('practice', _('Practice Exercise')),
        ('challenge', _('Challenge')),
        ('learning_path', _('Learning Path')),
    )
    
    URGENCY_LEVELS = (
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_recommendations'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    recommendation_type = models.CharField(max_length=30, choices=RECOMMENDATION_TYPES)
    urgency = models.CharField(max_length=10, choices=URGENCY_LEVELS, default='medium')
    
    # For linking to specific content
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    confidence_score = models.FloatField(
        default=0.7,
        help_text=_("AI confidence in this recommendation (0-1)")
    )
    
    class Meta:
        verbose_name = _('AI Learning Recommendation')
        verbose_name_plural = _('AI Learning Recommendations')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} for {self.user.username}"
    
    @property
    def is_expired(self):
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False


class UserEngagement(models.Model):
    """
    Metrics for user engagement with the platform.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='engagement_metrics'
    )
    date = models.DateField()
    time_spent = models.PositiveIntegerField(help_text=_("Time spent in seconds"))
    pages_visited = models.PositiveIntegerField(default=0)
    lessons_completed = models.PositiveIntegerField(default=0)
    quizzes_taken = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = _('User Engagement')
        verbose_name_plural = _('User Engagements')
        unique_together = ('user', 'date')
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.user.username} - {self.date}"


class UserPerformance(models.Model):
    """
    Track user performance metrics over time.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance_metrics',
        verbose_name=_('User')
    )
    date = models.DateField(_('Date'))
    quiz_average_score = models.FloatField(_('Quiz Average Score'), null=True, blank=True)
    time_spent_minutes = models.PositiveIntegerField(_('Time Spent (minutes)'), default=0)
    content_completed_count = models.PositiveIntegerField(_('Content Completed Count'), default=0)
    points_earned = models.PositiveIntegerField(_('Points Earned'), default=0)
    
    class Meta:
        verbose_name = _('User Performance')
        verbose_name_plural = _('User Performances')
        unique_together = [['user', 'date']]
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.user.username} - Performance on {self.date}"


class ContentDifficulty(models.Model):
    """
    Track difficulty ratings for content.
    """
    CONTENT_TYPES = (
        ('lesson', _('Lesson')),
        ('video', _('Video')),
        ('quiz', _('Quiz')),
        ('question', _('Question')),
    )
    
    content_type = models.CharField(
        _('Content Type'),
        max_length=10,
        choices=CONTENT_TYPES
    )
    content_id = models.PositiveIntegerField(_('Content ID'))
    difficulty_score = models.FloatField(_('Difficulty Score'), default=0.0)
    rating_count = models.PositiveIntegerField(_('Rating Count'), default=0)
    last_updated = models.DateTimeField(_('Last Updated'), auto_now=True)
    
    class Meta:
        verbose_name = _('Content Difficulty')
        verbose_name_plural = _('Content Difficulties')
        unique_together = [['content_type', 'content_id']]
    
    def __str__(self):
        return f"{self.get_content_type_display()} {self.content_id} - Difficulty: {self.difficulty_score}"


class UserContentDifficultyRating(models.Model):
    """
    Individual user ratings for content difficulty.
    """
    DIFFICULTY_CHOICES = (
        (1, _('Very Easy')),
        (2, _('Easy')),
        (3, _('Moderate')),
        (4, _('Difficult')),
        (5, _('Very Difficult')),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='difficulty_ratings',
        verbose_name=_('User')
    )
    content_difficulty = models.ForeignKey(
        ContentDifficulty,
        on_delete=models.CASCADE,
        related_name='user_ratings',
        verbose_name=_('Content Difficulty')
    )
    rating = models.PositiveSmallIntegerField(
        _('Rating'),
        choices=DIFFICULTY_CHOICES
    )
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('User Content Difficulty Rating')
        verbose_name_plural = _('User Content Difficulty Ratings')
        unique_together = [['user', 'content_difficulty']]
    
    def __str__(self):
        return f"{self.user.username} - {self.content_difficulty} - Rating: {self.rating}" 