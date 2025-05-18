from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django.contrib.auth.models import User


class Category(models.Model):
    """
    Course categories (e.g., Programming, Business, Design).
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(_('Icon Class'), max_length=50, blank=True, help_text=_('Font Awesome icon class'))
    
    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('courses:category_detail', args=[self.slug])
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Course(models.Model):
    """
    Main course model containing general information.
    """
    DIFFICULTY_CHOICES = (
        ('beginner', _('Beginner')),
        ('intermediate', _('Intermediate')),
        ('advanced', _('Advanced')),
    )
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    overview = models.TextField(blank=True)
    description = models.TextField()
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses_created'
    )
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='courses',
        null=True,
        blank=True
    )
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner'
    )
    prerequisites = models.TextField(blank=True)
    learning_outcomes = models.TextField(_('Learning Outcomes'))
    price = models.DecimalField(
        _('Price'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Course price (0 for free)')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='courses_enrolled',
        blank=True,
        through='Enrollment'
    )
    
    class Meta:
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('courses:course_detail', args=[self.slug])
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    @property
    def total_modules(self):
        return self.modules.count()
    
    @property
    def total_students(self):
        return self.students.count()
    
    @property
    def rating(self):
        reviews = self.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0
    
    def get_thumbnail_url(self):
        """Return the thumbnail URL or a default image URL if no thumbnail exists."""
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail.url
        return '/media/images/default_course.jpg'


class Module(models.Model):
    """
    Course modules containing lessons and activities.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = _('Module')
        verbose_name_plural = _('Modules')
        ordering = ['order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Content(models.Model):
    """
    Abstract base model for different types of content.
    """
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='contents',
        verbose_name=_('Module')
    )
    title = models.CharField(_('Title'), max_length=200)
    order = models.PositiveIntegerField(_('Order'), default=0)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['order']


class Lesson(Content):
    """
    Text-based lesson content.
    """
    content = models.TextField(_('Content'))
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    
    class Meta:
        verbose_name = _('Lesson')
        verbose_name_plural = _('Lessons')
    
    def __str__(self):
        return self.title


class Video(Content):
    """
    Video lesson content.
    """
    url = models.URLField(_('Video URL'))
    description = models.TextField(_('Description'), blank=True)
    duration = models.PositiveIntegerField(_('Duration (seconds)'), default=0)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='videos')
    
    class Meta:
        verbose_name = _('Video')
        verbose_name_plural = _('Videos')
    
    def __str__(self):
        return self.title


class Quiz(Content):
    """
    Quiz content for assessment.
    """
    description = models.TextField(_('Description'))
    time_limit = models.PositiveIntegerField(_('Time Limit (minutes)'), default=30)
    passing_score = models.PositiveIntegerField(_('Passing Score (%)'), default=70)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='quizzes')
    
    class Meta:
        verbose_name = _('Quiz')
        verbose_name_plural = _('Quizzes')
    
    def __str__(self):
        return self.title


class Question(models.Model):
    """
    Quiz questions.
    """
    QUESTION_TYPES = (
        ('multiple_choice', _('Multiple Choice')),
        ('true_false', _('True/False')),
        ('short_answer', _('Short Answer')),
    )
    
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    title = models.CharField(_('Question Title'), max_length=200, default='')
    text = models.TextField(_('Question Text'))
    question_type = models.CharField(
        _('Question Type'),
        max_length=20,
        choices=QUESTION_TYPES,
        default='multiple_choice'
    )
    points = models.PositiveIntegerField(_('Points'), default=1)
    order = models.PositiveIntegerField(_('Order'), default=0)
    explanation = models.TextField(
        blank=True,
        help_text=_("Explanation to show after answering")
    )
    
    class Meta:
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['order']
    
    def __str__(self):
        return f"{self.quiz.title} - Question {self.order}"


class Answer(models.Model):
    """
    Possible answers for quiz questions.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name=_('Question')
    )
    text = models.CharField(_('Answer Text'), max_length=255)
    is_correct = models.BooleanField(_('Correct Answer'), default=False)
    
    class Meta:
        verbose_name = _('Answer')
        verbose_name_plural = _('Answers')
    
    def __str__(self):
        return f"{self.question.text[:30]}... - {self.text[:30]}..."


class Enrollment(models.Model):
    """
    Track student enrollments in courses.
    """
    STATUS_CHOICES = (
        ('enrolled', 'Enrolled'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    )
    
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enrolled')
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['student', 'course']]
        
    def __str__(self):
        return f"{self.student.username} enrolled in {self.course.title}"
    
    def save(self, *args, **kwargs):
        # Set completed_at when status changes to completed
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)


class Progress(models.Model):
    """
    Tracking student progress through course content.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='progress'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='progress'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='progress'
    )
    completed_lessons = models.ManyToManyField(
        Lesson,
        blank=True,
        related_name='completed_by'
    )
    completed_videos = models.ManyToManyField(
        Video,
        related_name='completed_by',
        verbose_name=_('Completed Videos'),
        blank=True
    )
    completed_quizzes = models.ManyToManyField(
        Quiz,
        blank=True,
        related_name='completed_by'
    )
    last_accessed = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Progress')
        verbose_name_plural = _('Progress')
        unique_together = ('student', 'course', 'module')
    
    def __str__(self):
        return f"{self.student.username} - {self.course.title} - {self.module.title}"
    
    @property
    def completion_percentage(self):
        """Calculate the completion percentage for this module."""
        total_items = self.module.lessons.count() + self.module.videos.count() + self.module.quizzes.count()
        if total_items == 0:
            return 0
        
        completed_items = self.completed_lessons.count() + self.completed_videos.count() + self.completed_quizzes.count()
        return (completed_items / total_items) * 100


class QuizAttempt(models.Model):
    """
    Model to store quiz attempts by users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    score = models.FloatField(default=0.0)
    max_score = models.FloatField(default=0.0)
    completed = models.BooleanField(default=False)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _('Quiz Attempt')
        verbose_name_plural = _('Quiz Attempts')
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user.username}'s attempt on {self.quiz.title}"
    
    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0
    
    @property
    def score_percentage(self):
        """Calculate the percentage score"""
        if self.max_score > 0:
            return (self.score / self.max_score) * 100
        return 0


class QuizAnswer(models.Model):
    """
    Model to store user's answers to quiz questions.
    """
    quiz_attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='user_answers'
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name='user_selections',
        null=True,
        blank=True
    )
    is_correct = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _('Quiz Answer')
        verbose_name_plural = _('Quiz Answers')
    
    def __str__(self):
        return f"Answer to {self.question.text} by {self.quiz_attempt.user.username}"


class PersonalizedQuizAttempt(models.Model):
    """
    Model to store attempts at personalized quizzes.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='personalized_quiz_attempts'
    )
    title = models.CharField(max_length=200)
    score = models.FloatField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Personalized Quiz Attempt')
        verbose_name_plural = _('Personalized Quiz Attempts')
    
    def __str__(self):
        return f"{self.user.username} - {self.title} - {self.created_at.strftime('%Y-%m-%d')}"


class Option(models.Model):
    """
    Options for quiz questions.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options'
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _('Option')
        verbose_name_plural = _('Options')
    
    def __str__(self):
        return f"{self.question.text[:30]}... - {self.text[:30]}..."


class StudySession(models.Model):
    """
    Model to store study sessions for the study planner.
    """
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_sessions'
    )
    title = models.CharField(max_length=200)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='study_sessions',
        null=True,
        blank=True
    )
    date = models.DateField()
    start_time = models.TimeField()
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    notes = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Study Session')
        verbose_name_plural = _('Study Sessions')
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.title} - {self.date}"
    
    @property
    def end_time(self):
        """Calculate the end time based on start time and duration."""
        from datetime import datetime, timedelta
        start_datetime = datetime.combine(datetime.today(), self.start_time)
        end_datetime = start_datetime + timedelta(minutes=self.duration)
        return end_datetime.time()


class StudyGoal(models.Model):
    """
    Model to store study goals for users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_goals'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    progress = models.PositiveIntegerField(default=0, help_text="Progress percentage (0-100)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Study Goal')
        verbose_name_plural = _('Study Goals')
        ordering = ['target_date', 'created_at']
    
    def __str__(self):
        return self.title


class StudyPreference(models.Model):
    """
    Model to store study preferences for users.
    """
    TIME_PREFERENCES = (
        ('morning', 'Morning (6 AM - 12 PM)'),
        ('afternoon', 'Afternoon (12 PM - 5 PM)'),
        ('evening', 'Evening (5 PM - 10 PM)'),
        ('night', 'Night (10 PM - 6 AM)'),
        ('flexible', 'Flexible'),
    )
    
    SESSION_LENGTH_PREFERENCES = (
        ('short', 'Short (15-30 minutes)'),
        ('medium', 'Medium (30-60 minutes)'),
        ('long', 'Long (60-90 minutes)'),
        ('extended', 'Extended (90+ minutes)'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_preferences'
    )
    daily_goal = models.FloatField(default=4.0, help_text="Daily study goal in hours")
    weekly_goal = models.FloatField(default=20.0, help_text="Weekly study goal in hours")
    preferred_time = models.CharField(max_length=20, choices=TIME_PREFERENCES, default='flexible')
    session_length = models.CharField(max_length=20, choices=SESSION_LENGTH_PREFERENCES, default='medium')
    email_notifications = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=True)
    reminder_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Study Preference')
        verbose_name_plural = _('Study Preferences')
    
    def __str__(self):
        return f"{self.user.username}'s Study Preferences"


class StudyStreak(models.Model):
    """
    Model to track study streaks for users.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_streak'
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_study_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Study Streak')
        verbose_name_plural = _('Study Streaks')
    
    def __str__(self):
        return f"{self.user.username}'s Study Streak: {self.current_streak} days"
    
    def update_streak(self, study_date):
        """Update the streak based on a new study date."""
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        
        # Convert study_date to date object if it's a string
        if isinstance(study_date, str):
            study_date = datetime.strptime(study_date, '%Y-%m-%d').date()
        
        # If this is the first study date
        if not self.last_study_date:
            self.current_streak = 1
            self.longest_streak = 1
            self.last_study_date = study_date
            self.save()
            return
        
        # If the study date is the same as the last study date, no change
        if study_date == self.last_study_date:
            return
        
        # If the study date is before the last study date, no change
        if study_date < self.last_study_date:
            return
        
        # If the study date is one day after the last study date, increment streak
        if study_date == self.last_study_date + timedelta(days=1):
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
            self.last_study_date = study_date
            self.save()
            return
        
        # If the study date is today and the last study date was yesterday, increment streak
        if study_date == today and self.last_study_date == today - timedelta(days=1):
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
            self.last_study_date = study_date
            self.save()
            return
        
        # If there's a gap, reset the streak
        self.current_streak = 1
        self.last_study_date = study_date
        self.save()


class Deadline(models.Model):
    """
    Model to store deadlines for courses and assignments.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='deadlines'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='deadlines',
        null=True,
        blank=True
    )
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Deadline')
        verbose_name_plural = _('Deadlines')
        ordering = ['due_date']
    
    def __str__(self):
        return self.title
    
    @property
    def days_left(self):
        """Calculate the number of days left until the deadline."""
        from datetime import datetime
        today = datetime.now().date()
        delta = self.due_date - today
        return delta.days


class FocusArea(models.Model):
    """
    Model to store focus areas for users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='focus_areas'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    progress = models.PositiveIntegerField(default=0, help_text="Progress percentage (0-100)")
    hours_spent = models.FloatField(default=0.0, help_text="Hours spent on this focus area")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Focus Area')
        verbose_name_plural = _('Focus Areas')
        ordering = ['-progress']
    
    def __str__(self):
        return self.title 