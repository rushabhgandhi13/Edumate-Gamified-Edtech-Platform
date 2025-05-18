from rest_framework import serializers
from django.contrib.auth import get_user_model
from courses.models import (
    Category, Course, Module, Lesson, Video, Quiz,
    Question, Answer, Enrollment, Progress, QuizAttempt
)
from gamification.models import (
    Badge, UserBadge, Achievement, UserAchievement,
    Challenge, UserChallenge, PointsTransaction, Streak
)
from analytics.models import (
    UserActivity, LearningInsight, UserPerformance,
    ContentDifficulty, UserContentDifficultyRating
)

User = get_user_model()


# User Serializers
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'user_type', 
                  'points', 'level', 'streak_days', 'date_joined']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = User.profile.related.related_model
        fields = ['user', 'interests', 'skills', 'learning_goals', 'preferred_learning_style',
                  'content_difficulty_preference']


# Course Serializers
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon']


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    instructor = UserSerializer(read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'title', 'slug', 'category', 'instructor', 'overview', 
                  'difficulty', 'thumbnail', 'total_modules', 'total_students']


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order']


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'order', 'created_at', 'updated_at']


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['id', 'title', 'url', 'duration', 'order', 'created_at', 'updated_at']


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'text', 'is_correct']


class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'points', 'order', 'answers']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'time_limit', 'passing_score', 
                  'order', 'created_at', 'updated_at', 'questions']


class CourseDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    instructor = UserSerializer(read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'title', 'slug', 'category', 'instructor', 'overview', 
                  'description', 'difficulty', 'prerequisites', 'learning_outcomes',
                  'thumbnail', 'created_at', 'updated_at', 'is_published',
                  'total_modules', 'total_students', 'modules']


class EnrollmentSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'date_enrolled', 'status', 'completion_date']


class ProgressSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)
    module = ModuleSerializer(read_only=True)
    
    class Meta:
        model = Progress
        fields = ['id', 'student', 'course', 'module', 'last_accessed', 'completion_percentage']


class QuizAttemptSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    quiz = QuizSerializer(read_only=True)
    
    class Meta:
        model = QuizAttempt
        fields = ['id', 'student', 'quiz', 'score', 'max_score', 'score_percentage',
                  'started_at', 'completed_at', 'passed']


# Gamification Serializers
class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'name', 'description', 'icon', 'badge_type', 'points', 'created_at']


class UserBadgeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    badge = BadgeSerializer(read_only=True)
    
    class Meta:
        model = UserBadge
        fields = ['id', 'user', 'badge', 'awarded_at']


class AchievementSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    
    class Meta:
        model = Achievement
        fields = ['id', 'name', 'description', 'achievement_type', 'badge', 
                  'points', 'threshold', 'created_at']


class UserAchievementSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    achievement = AchievementSerializer(read_only=True)
    
    class Meta:
        model = UserAchievement
        fields = ['id', 'user', 'achievement', 'unlocked_at']


class ChallengeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    
    class Meta:
        model = Challenge
        fields = ['id', 'title', 'description', 'challenge_type', 'points', 
                  'badge', 'start_date', 'end_date', 'is_active', 'is_ongoing']


class UserChallengeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    challenge = ChallengeSerializer(read_only=True)
    
    class Meta:
        model = UserChallenge
        fields = ['id', 'user', 'challenge', 'status', 'progress', 
                  'accepted_at', 'completed_at']


class PointsTransactionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PointsTransaction
        fields = ['id', 'user', 'points', 'transaction_type', 'description', 'timestamp']


class StreakSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Streak
        fields = ['id', 'user', 'current_streak', 'longest_streak', 'last_activity_date']


# Analytics Serializers
class UserActivitySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserActivity
        fields = ['id', 'user', 'activity_type', 'timestamp', 'details']


class LearningInsightSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = LearningInsight
        fields = ['id', 'user', 'insight_type', 'content', 'generated_at', 
                  'is_read', 'relevance_score']


class UserPerformanceSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserPerformance
        fields = ['id', 'user', 'date', 'quiz_average_score', 'time_spent_minutes',
                  'content_completed_count', 'points_earned']


class ContentDifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentDifficulty
        fields = ['id', 'content_type', 'content_id', 'difficulty_score', 
                  'rating_count', 'last_updated']


class UserContentDifficultyRatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    content_difficulty = ContentDifficultySerializer(read_only=True)
    
    class Meta:
        model = UserContentDifficultyRating
        fields = ['id', 'user', 'content_difficulty', 'rating', 'timestamp'] 