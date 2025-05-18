from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# User routes
router.register(r'users', views.UserViewSet)
router.register(r'profiles', views.UserProfileViewSet)

# Course routes
router.register(r'categories', views.CategoryViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'modules', views.ModuleViewSet)
router.register(r'lessons', views.LessonViewSet)
router.register(r'videos', views.VideoViewSet)
router.register(r'quizzes', views.QuizViewSet)
router.register(r'questions', views.QuestionViewSet)
router.register(r'answers', views.AnswerViewSet)
router.register(r'enrollments', views.EnrollmentViewSet, basename='enrollment')
router.register(r'progress', views.ProgressViewSet, basename='progress')
router.register(r'quiz-attempts', views.QuizAttemptViewSet, basename='quizattempt')

# Gamification routes
router.register(r'badges', views.BadgeViewSet)
router.register(r'user-badges', views.UserBadgeViewSet, basename='userbadge')
router.register(r'achievements', views.AchievementViewSet)
router.register(r'user-achievements', views.UserAchievementViewSet, basename='userachievement')
router.register(r'challenges', views.ChallengeViewSet, basename='challenge')
router.register(r'user-challenges', views.UserChallengeViewSet, basename='userchallenge')
router.register(r'points-transactions', views.PointsTransactionViewSet, basename='pointstransaction')
router.register(r'streaks', views.StreakViewSet, basename='streak')

# Analytics routes
router.register(r'user-activities', views.UserActivityViewSet, basename='useractivity')
router.register(r'learning-insights', views.LearningInsightViewSet, basename='learninginsight')
router.register(r'user-performance', views.UserPerformanceViewSet, basename='userperformance')
router.register(r'content-difficulty', views.ContentDifficultyViewSet)
router.register(r'difficulty-ratings', views.UserContentDifficultyRatingViewSet, basename='difficultyrating')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
] 