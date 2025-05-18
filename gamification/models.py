from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Point(models.Model):
    """
    Points earned by users for various activities.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_earned'
    )
    points = models.IntegerField(default=0)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Point')
        verbose_name_plural = _('Points')
    
    def __str__(self):
        return f"{self.user.username}: {self.points} points - {self.description}"

class Badge(models.Model):
    """Model for user badges"""
    BADGE_TYPES = (
        ('achievement', 'Achievement'),
        ('progress', 'Progress'),
        ('activity', 'Activity'),
        ('special', 'Special'),
        ('mastery', 'Mastery'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    image = models.ImageField(upload_to='badges/', blank=True, null=True)
    points_required = models.PositiveIntegerField(default=0)
    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES, default='achievement')
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through='UserBadge', related_name='badge_set')
    
    def __str__(self):
        return self.name

class Achievement(models.Model):
    """Model for user achievements"""
    ACHIEVEMENT_TYPES = (
        ('quiz_score', 'Quiz Score'),
        ('course_completion', 'Course Completion'),
        ('streak', 'Streak'),
        ('activity', 'Activity'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    points_reward = models.PositiveIntegerField(default=10)
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES, default='activity')
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through='UserAchievement', related_name='achievement_set')
    
    def __str__(self):
        return self.name

class UserBadge(models.Model):
    """Model to track badges earned by users"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'badge')
    
    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"

class UserAchievement(models.Model):
    """Model to track achievements earned by users"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    date_earned = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'achievement')
    
    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"

class ProgressBadge(models.Model):
    """Model for defining progress-based badges that are automatically awarded when users reach milestones"""
    PROGRESS_TYPES = (
        ('course_completion', 'Course Completion'),
        ('module_completion', 'Module Completion'),
        ('lesson_completion', 'Lesson Completion'),
        ('quiz_performance', 'Quiz Performance'),
        ('activity_count', 'Activity Count'),
        ('points_milestone', 'Points Milestone'),
    )
    
    badge = models.OneToOneField(Badge, on_delete=models.CASCADE, related_name='progress_criteria')
    progress_type = models.CharField(max_length=30, choices=PROGRESS_TYPES)
    threshold = models.PositiveIntegerField(help_text="Target value to achieve for earning the badge")
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, null=True, blank=True, 
                              help_text="If this badge is specific to a course")
    module = models.ForeignKey('courses.Module', on_delete=models.SET_NULL, null=True, blank=True,
                              help_text="If this badge is specific to a module")
    
    # For quiz performance badges
    min_score = models.PositiveIntegerField(null=True, blank=True, 
                                          help_text="Minimum quiz score required (percentage)")
    
    # Difficulty level
    difficulty = models.CharField(max_length=10, choices=[
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ], default='medium')
    
    def __str__(self):
        return f"Progress criteria for {self.badge.name}"

class Challenge(models.Model):
    """Model for challenges that users can complete"""
    DIFFICULTY_CHOICES = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    points_reward = models.PositiveIntegerField(default=20)
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class UserChallenge(models.Model):
    """Model to track user progress on challenges"""
    STATUS_CHOICES = (
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenges')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='not_started')
    progress = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'challenge')
    
    def __str__(self):
        return f"{self.user.username} - {self.challenge.name} ({self.status})"

class Streak(models.Model):
    """Model to track user login streaks"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.current_streak} days"
    
    def update_streak(self):
        """Update the user's streak based on their last activity"""
        today = timezone.now().date()
        
        if not self.last_activity_date:
            # First activity
            self.current_streak = 1
            self.longest_streak = 1
        elif self.last_activity_date == today:
            # Already logged in today
            pass
        elif (today - self.last_activity_date).days == 1:
            # Consecutive day
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
        else:
            # Streak broken
            self.current_streak = 1
        
        self.last_activity_date = today
        self.save()
        
        # Check for streak-based badges
        self.check_and_award_streak_badges()
    
    def check_and_award_streak_badges(self):
        """Check if user is eligible for streak-based badges and award them"""
        # Check for the Consistent Learner badge (3 consecutive days)
        if self.current_streak >= 3:
            try:
                badge = Badge.objects.get(name='Consistent Learner')
                UserBadge.objects.get_or_create(
                    user=self.user,
                    badge=badge
                )
                
                # Also create a points transaction if points_required > 0
                if badge.points_required > 0:
                    PointsTransaction.objects.create(
                        user=self.user,
                        points=badge.points_required,
                        transaction_type='bonus',
                        description=f"Earned {badge.name} badge for {self.current_streak} day streak"
                    )
            except Badge.DoesNotExist:
                # Badge doesn't exist yet
                pass

class Leaderboard(models.Model):
    """Model for leaderboard entries"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-points']
    
    def __str__(self):
        return f"{self.user.username} - {self.points} points (Rank: {self.rank})"

class PointsTransaction(models.Model):
    """Model to track points transactions for users"""
    TRANSACTION_TYPES = (
        ('earned', 'Earned'),
        ('spent', 'Spent'),
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_transactions')
    points = models.IntegerField()
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} {self.transaction_type} {self.points} points" 