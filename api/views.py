from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

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

from .serializers import (
    # User serializers
    UserSerializer, UserProfileSerializer,
    
    # Course serializers
    CategorySerializer, CourseListSerializer, CourseDetailSerializer,
    ModuleSerializer, LessonSerializer, VideoSerializer,
    QuizSerializer, QuestionSerializer, AnswerSerializer,
    EnrollmentSerializer, ProgressSerializer, QuizAttemptSerializer,
    
    # Gamification serializers
    BadgeSerializer, UserBadgeSerializer, AchievementSerializer,
    UserAchievementSerializer, ChallengeSerializer, UserChallengeSerializer,
    PointsTransactionSerializer, StreakSerializer,
    
    # Analytics serializers
    UserActivitySerializer, LearningInsightSerializer, UserPerformanceSerializer,
    ContentDifficultySerializer, UserContentDifficultyRatingSerializer
)

User = get_user_model()


# Custom permissions
class IsInstructorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow instructors to edit courses.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_instructor()

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.instructor == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Get the owner field name based on the model
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'student'):
            return obj.student == request.user
        return False


# User viewsets
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows users to be viewed.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_type']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get the current user's information.
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """
        Get the top users by points.
        """
        top_users = User.objects.filter(is_active=True).order_by('-points')[:50]
        serializer = self.get_serializer(top_users, many=True)
        return Response(serializer.data)


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows user profiles to be viewed.
    """
    queryset = User.profile.related.related_model.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """
        Get the current user's profile.
        """
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)


# Course viewsets
class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows categories to be viewed or edited.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()


class CourseViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows courses to be viewed or edited.
    """
    queryset = Course.objects.all()
    serializer_class = CourseListSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'difficulty', 'is_published']
    search_fields = ['title', 'overview', 'description']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseListSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # If not authenticated, only show published courses
        if not user.is_authenticated:
            return Course.objects.filter(is_published=True)
        
        # If instructor, show their courses and published courses
        if user.is_instructor():
            return Course.objects.filter(
                models.Q(instructor=user) | models.Q(is_published=True)
            ).distinct()
        
        # Otherwise, only show published courses
        return Course.objects.filter(is_published=True)
    
    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)
    
    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """
        Enroll the current user in this course.
        """
        course = self.get_object()
        user = request.user
        
        # Check if already enrolled
        if Enrollment.objects.filter(student=user, course=course).exists():
            return Response(
                {'detail': 'You are already enrolled in this course.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create enrollment
        enrollment = Enrollment.objects.create(
            student=user,
            course=course,
            status='enrolled'
        )
        
        # Create progress records for each module
        for module in course.modules.all():
            Progress.objects.create(
                student=user,
                course=course,
                module=module
            )
        
        # Add points for enrollment (gamification)
        user.points += 50
        user.save()
        
        # Create points transaction
        PointsTransaction.objects.create(
            user=user,
            points=50,
            transaction_type='earned',
            description=f"Enrolled in course: {course.title}"
        )
        
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def my_courses(self, request):
        """
        Get courses the current user is enrolled in.
        """
        enrollments = Enrollment.objects.filter(student=request.user)
        courses = [enrollment.course for enrollment in enrollments]
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def teaching(self, request):
        """
        Get courses the current user is teaching.
        """
        if not request.user.is_instructor():
            return Response(
                {'detail': 'You are not an instructor.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        courses = Course.objects.filter(instructor=request.user)
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)


class ModuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows modules to be viewed or edited.
    """
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course']
    
    def get_queryset(self):
        course_id = self.request.query_params.get('course')
        if course_id:
            return Module.objects.filter(course_id=course_id).order_by('order')
        return Module.objects.all().order_by('order')
    
    def perform_create(self, serializer):
        course = get_object_or_404(Course, pk=self.request.data.get('course'))
        if course.instructor != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save(course=course)


class LessonViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows lessons to be viewed or edited.
    """
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['module']
    
    def get_queryset(self):
        module_id = self.request.query_params.get('module')
        if module_id:
            return Lesson.objects.filter(module_id=module_id).order_by('order')
        return Lesson.objects.all().order_by('order')
    
    def perform_create(self, serializer):
        module = get_object_or_404(Module, pk=self.request.data.get('module'))
        if module.course.instructor != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save(module=module)


class VideoViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows videos to be viewed or edited.
    """
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['module']
    
    def get_queryset(self):
        module_id = self.request.query_params.get('module')
        if module_id:
            return Video.objects.filter(module_id=module_id).order_by('order')
        return Video.objects.all().order_by('order')
    
    def perform_create(self, serializer):
        module = get_object_or_404(Module, pk=self.request.data.get('module'))
        if module.course.instructor != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save(module=module)


class QuizViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows quizzes to be viewed or edited.
    """
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['module']
    
    def get_queryset(self):
        module_id = self.request.query_params.get('module')
        if module_id:
            return Quiz.objects.filter(module_id=module_id).order_by('order')
        return Quiz.objects.all().order_by('order')
    
    def perform_create(self, serializer):
        module = get_object_or_404(Module, pk=self.request.data.get('module'))
        if module.course.instructor != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save(module=module)


class QuestionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows questions to be viewed or edited.
    """
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quiz']
    
    def get_queryset(self):
        quiz_id = self.request.query_params.get('quiz')
        if quiz_id:
            return Question.objects.filter(quiz_id=quiz_id).order_by('order')
        return Question.objects.all().order_by('order')
    
    def perform_create(self, serializer):
        quiz = get_object_or_404(Quiz, pk=self.request.data.get('quiz'))
        if quiz.module.course.instructor != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save(quiz=quiz)


class AnswerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows answers to be viewed or edited.
    """
    queryset = Answer.objects.all()
    serializer_class = AnswerSerializer
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['question']
    
    def perform_create(self, serializer):
        question = get_object_or_404(Question, pk=self.request.data.get('question'))
        if question.quiz.module.course.instructor != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save(question=question)


class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows enrollments to be viewed.
    """
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course', 'status']
    
    def get_queryset(self):
        user = self.request.user
        
        # If instructor, show enrollments for their courses
        if user.is_instructor():
            return Enrollment.objects.filter(course__instructor=user)
        
        # Otherwise, only show user's own enrollments
        return Enrollment.objects.filter(student=user)


class ProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows progress to be viewed.
    """
    serializer_class = ProgressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course', 'module']
    
    def get_queryset(self):
        user = self.request.user
        
        # If instructor, show progress for their courses
        if user.is_instructor():
            return Progress.objects.filter(course__instructor=user)
        
        # Otherwise, only show user's own progress
        return Progress.objects.filter(student=user)


class QuizAttemptViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows quiz attempts to be viewed or created.
    """
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quiz', 'passed']
    
    def get_queryset(self):
        user = self.request.user
        
        # If instructor, show attempts for their quizzes
        if user.is_instructor():
            return QuizAttempt.objects.filter(quiz__module__course__instructor=user)
        
        # Otherwise, only show user's own attempts
        return QuizAttempt.objects.filter(student=user)
    
    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


# Gamification viewsets
class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows badges to be viewed.
    """
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['badge_type']
    search_fields = ['name', 'description']


class UserBadgeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows user badges to be viewed.
    """
    serializer_class = UserBadgeSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['badge']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all user badges
        if user.is_staff:
            return UserBadge.objects.all()
        
        # Otherwise, only show user's own badges
        return UserBadge.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_badges(self, request):
        """
        Get the current user's badges.
        """
        badges = UserBadge.objects.filter(user=request.user)
        serializer = self.get_serializer(badges, many=True)
        return Response(serializer.data)


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows achievements to be viewed.
    """
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['achievement_type']
    search_fields = ['name', 'description']


class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows user achievements to be viewed.
    """
    serializer_class = UserAchievementSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['achievement']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all user achievements
        if user.is_staff:
            return UserAchievement.objects.all()
        
        # Otherwise, only show user's own achievements
        return UserAchievement.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_achievements(self, request):
        """
        Get the current user's achievements.
        """
        achievements = UserAchievement.objects.filter(user=request.user)
        serializer = self.get_serializer(achievements, many=True)
        return Response(serializer.data)


class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows challenges to be viewed.
    """
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['challenge_type', 'is_active']
    search_fields = ['title', 'description']
    
    def get_queryset(self):
        # Only show active challenges
        return Challenge.objects.filter(is_active=True)
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept a challenge.
        """
        challenge = self.get_object()
        user = request.user
        
        # Check if challenge is still active
        if not challenge.is_ongoing:
            return Response(
                {'detail': 'This challenge is no longer active.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already accepted
        if UserChallenge.objects.filter(user=user, challenge=challenge).exists():
            return Response(
                {'detail': 'You have already accepted this challenge.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user challenge
        user_challenge = UserChallenge.objects.create(
            user=user,
            challenge=challenge,
            status='accepted'
        )
        
        serializer = UserChallengeSerializer(user_challenge)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows user challenges to be viewed.
    """
    serializer_class = UserChallengeSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['challenge', 'status']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all user challenges
        if user.is_staff:
            return UserChallenge.objects.all()
        
        # Otherwise, only show user's own challenges
        return UserChallenge.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_challenges(self, request):
        """
        Get the current user's challenges.
        """
        challenges = UserChallenge.objects.filter(user=request.user)
        serializer = self.get_serializer(challenges, many=True)
        return Response(serializer.data)


class PointsTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows points transactions to be viewed.
    """
    serializer_class = PointsTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['transaction_type']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all transactions
        if user.is_staff:
            return PointsTransaction.objects.all()
        
        # Otherwise, only show user's own transactions
        return PointsTransaction.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_transactions(self, request):
        """
        Get the current user's points transactions.
        """
        transactions = PointsTransaction.objects.filter(user=request.user).order_by('-timestamp')
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)


class StreakViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows streaks to be viewed.
    """
    serializer_class = StreakSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all streaks
        if user.is_staff:
            return Streak.objects.all()
        
        # Otherwise, only show user's own streak
        return Streak.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_streak(self, request):
        """
        Get the current user's streak.
        """
        streak, created = Streak.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(streak)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_streak(self, request):
        """
        Update the current user's streak.
        """
        streak, created = Streak.objects.get_or_create(user=request.user)
        streak.update_streak()
        serializer = self.get_serializer(streak)
        return Response(serializer.data)


# Analytics viewsets
class UserActivityViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows user activities to be viewed or created.
    """
    serializer_class = UserActivitySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['activity_type']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all activities
        if user.is_staff:
            return UserActivity.objects.all()
        
        # Otherwise, only show user's own activities
        return UserActivity.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """
        Get the current user's activities.
        """
        activities = UserActivity.objects.filter(user=request.user).order_by('-timestamp')
        serializer = self.get_serializer(activities, many=True)
        return Response(serializer.data)


class LearningInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows learning insights to be viewed.
    """
    serializer_class = LearningInsightSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['insight_type', 'is_read']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all insights
        if user.is_staff:
            return LearningInsight.objects.all()
        
        # Otherwise, only show user's own insights
        return LearningInsight.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_insights(self, request):
        """
        Get the current user's learning insights.
        """
        insights = LearningInsight.objects.filter(user=request.user).order_by('-generated_at')
        serializer = self.get_serializer(insights, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """
        Mark an insight as read.
        """
        insight = self.get_object()
        insight.is_read = True
        insight.save()
        serializer = self.get_serializer(insight)
        return Response(serializer.data)


class UserPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows user performance to be viewed.
    """
    serializer_class = UserPerformanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all performance records
        if user.is_staff:
            return UserPerformance.objects.all()
        
        # Otherwise, only show user's own performance records
        return UserPerformance.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def my_performance(self, request):
        """
        Get the current user's performance records.
        """
        performance = UserPerformance.objects.filter(user=request.user).order_by('-date')
        serializer = self.get_serializer(performance, many=True)
        return Response(serializer.data)


class ContentDifficultyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows content difficulty to be viewed.
    """
    queryset = ContentDifficulty.objects.all()
    serializer_class = ContentDifficultySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['content_type']


class UserContentDifficultyRatingViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows user content difficulty ratings to be viewed or created.
    """
    serializer_class = UserContentDifficultyRatingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['content_difficulty']
    
    def get_queryset(self):
        user = self.request.user
        
        # If admin, show all ratings
        if user.is_staff:
            return UserContentDifficultyRating.objects.all()
        
        # Otherwise, only show user's own ratings
        return UserContentDifficultyRating.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user) 