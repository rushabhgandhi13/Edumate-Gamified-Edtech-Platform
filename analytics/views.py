from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, TemplateView
from django.http import JsonResponse
from django.db.models import Count, Avg, Sum, F, Q
from django.utils import timezone
from datetime import timedelta
import json
import openai
import numpy as np
from collections import Counter
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.conf import settings

from .models import (
    UserActivity, LearningInsight, UserPerformance,
    ContentDifficulty, UserContentDifficultyRating,
    LearningStyle, AILearningRecommendation
)
from courses.models import Enrollment, Progress, QuizAttempt, Course, Lesson, Quiz
from gamification.models import UserAchievement, UserBadge, PointsTransaction, Badge
from .utils import (
    generate_learning_insights, generate_learning_recommendations,
    detect_learning_style, get_user_learning_data
)


@login_required
def dashboard(request):
    """
    User analytics dashboard showing learning progress and insights.
    """
    user = request.user
    current_date = timezone.now().date()
    month_before = current_date - timedelta(days=30)
    
    insights = LearningInsight.objects.filter(
        user=user, 
        created_at__date__gte=month_before
    ).order_by('-relevance_score')[:3]
    
    recommendations = AILearningRecommendation.objects.filter(
        user=user, 
        expires_at__gte=timezone.now()
    ).order_by('-urgency', '-confidence_score')[:3]
    
    quiz_data = QuizAttempt.objects.filter(user=user)
    recent_quizzes = quiz_data.filter(
        completed_at__date__gte=month_before
    ).order_by('-completed_at')
    
    quiz_metrics = {
        'total_count': quiz_data.count(),
        'passed_count': quiz_data.filter(passed=True).count(),
        'recent_count': recent_quizzes.count(),
        'avg_score': quiz_data.aggregate(avg=Avg('score'))['avg'] or 0,
        'recent_avg': recent_quizzes.aggregate(avg=Avg('score'))['avg'] or 0,
        'recent_attempts': recent_quizzes[:5],
    }
    
    enrollments = Enrollment.objects.filter(student=user)
    active_courses = enrollments.filter(status='active')
    
    course_metrics = {
        'total_count': enrollments.count(),
        'active_count': active_courses.count(),
        'completed_count': enrollments.filter(status='completed').count(),
        'recent_courses': active_courses.order_by('-enrolled_at')[:3],
    }
    
    daily_stats = UserPerformance.objects.filter(
        user=user,
        date__gte=month_before
    ).order_by('date')
    
    performance_data = []
    point_data = []
    
    for stat in daily_stats:
        performance_data.append({
            'date': stat.date.strftime('%Y-%m-%d'),
            'score': stat.quiz_average_score,
            'time': stat.time_spent_minutes,
            'completed': stat.content_completed_count,
        })
        
        point_data.append({
            'date': stat.date.strftime('%Y-%m-%d'),
            'points': stat.points_earned,
        })
    
    study_streaks = []
    current_streak = 0
    best_streak = 0
    
    for i in range((current_date - month_before).days + 1):
        check_date = month_before + timedelta(days=i)
        day_active = UserActivity.objects.filter(
            user=user, 
            timestamp__date=check_date
        ).exists()
        
        if day_active:
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 0
    
    streak_data = {
        'current': current_streak,
        'best': best_streak
    }
    
    learning_style = None
    try:
        learning_style = LearningStyle.objects.get(user=user)
    except LearningStyle.DoesNotExist:
        learning_style = detect_learning_style(user)
    
    activity_counts = UserActivity.objects.filter(
        user=user, 
        timestamp__date__gte=month_before
    ).values('activity_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'insights': insights,
        'recommendations': recommendations,
        'quiz_metrics': quiz_metrics,
        'course_metrics': course_metrics,
        'performance_data': json.dumps(performance_data),
        'point_data': json.dumps(point_data),
        'streak_data': streak_data,
        'learning_style': learning_style,
        'activity_data': activity_counts,
    }
    
    return render(request, 'analytics/dashboard.html', context)


@login_required
def learning_insights(request):
    """
    Display AI-generated learning insights for the user.
    """
    user = request.user
    
    LearningInsight.objects.filter(user=user, read=False).update(read=True)
    
    insights = LearningInsight.objects.filter(user=user).order_by('-created_at')
    
    insight_types = {
        'learning_pattern': [],
        'engagement': [],
        'performance': [],
        'strength': [],
        'weakness': [],
        'improvement': [],
        'learning_style': [],
    }
    
    for insight in insights:
        if insight.insight_type in insight_types:
            insight_types[insight.insight_type].append(insight)
        else:
            insight_types.setdefault('other', []).append(insight)
    
    context = {
        'insight_types': insight_types,
    }
    
    return render(request, 'analytics/learning_insights.html', context)


@login_required
def generate_insight(request):
    """
    Generate a new AI insight for the user.
    """
    user = request.user
    
    try:
        insights = generate_learning_insights(user, insight_count=1)
        if insights:
            messages.success(request, "New learning insight generated successfully.")
        else:
            messages.warning(request, "Unable to generate new learning insight at this time.")
    except Exception as e:
        logger.error(f"Error generating insight for user {user.id}: {str(e)}")
        messages.error(request, "Something went wrong while generating your insight.")
    
    if 'next' in request.GET:
        return redirect(request.GET['next'])
    return redirect('learning_insights')


@login_required
def generate_recommendation(request):
    """
    Generate a new AI recommendation for the user.
    """
    user = request.user
    
    try:
        recommendations = generate_learning_recommendations(user, count=1)
        if recommendations:
            messages.success(request, "New learning recommendation generated successfully.")
        else:
            messages.warning(request, "Unable to generate new recommendation at this time.")
    except Exception as e:
        logger.error(f"Error generating recommendation for user {user.id}: {str(e)}")
        messages.error(request, "Something went wrong while generating your recommendation.")
    
    if 'next' in request.GET:
        return redirect(request.GET['next'])
    return redirect('dashboard')


@login_required
def learning_style_view(request):
    """
    Display and update a user's learning style information.
    """
    user = request.user
    
    learning_style, created = LearningStyle.objects.get_or_create(
        user=user,
        defaults={
            'primary_style': 'visual',
            'secondary_style': 'reading',
            'pace_preference': 'moderate',
            'prefers_group_learning': False,
            'prefers_practical_examples': True,
            'prefers_theory_first': False,
            'attention_span_minutes': 30,
            'confidence_level': 3
        }
    )
    
    if created or learning_style.confidence_level < 3:
        detected_style = detect_learning_style(user)
        if detected_style:
            learning_style = detected_style
    
    if request.method == 'POST':
        learning_style.primary_style = request.POST.get('primary_style', learning_style.primary_style)
        learning_style.secondary_style = request.POST.get('secondary_style', learning_style.secondary_style)
        learning_style.pace_preference = request.POST.get('pace_preference', learning_style.pace_preference)
        learning_style.prefers_group_learning = request.POST.get('prefers_group_learning', '') == 'on'
        learning_style.prefers_practical_examples = request.POST.get('prefers_practical_examples', '') == 'on'
        learning_style.prefers_theory_first = request.POST.get('prefers_theory_first', '') == 'on'
        
        try:
            learning_style.attention_span_minutes = int(request.POST.get('attention_span_minutes', 30))
        except ValueError:
            learning_style.attention_span_minutes = 30
        
        learning_style.manually_set = True
        learning_style.save()
        
        messages.success(request, "Your learning style preferences have been updated.")
        return redirect('learning_style')
    
    context = {
        'learning_style': learning_style,
    }
    
    return render(request, 'analytics/learning_style.html', context)


@login_required
def dismiss_recommendation(request, recommendation_id):
    """
    Mark a recommendation as dismissed.
    """
    if request.method != 'POST':
        return redirect('analytics:dashboard')
        
    recommendation = get_object_or_404(
        AILearningRecommendation, 
        id=recommendation_id,
        user=request.user
    )
    
    recommendation.dismissed = True
    recommendation.save()
    
    return redirect('analytics:dashboard')


@login_required
def complete_recommendation(request, recommendation_id):
    """
    Mark a recommendation as completed.
    """
    if request.method != 'POST':
        return redirect('analytics:dashboard')
        
    recommendation = get_object_or_404(
        AILearningRecommendation, 
        id=recommendation_id,
        user=request.user
    )
    
    recommendation.is_completed = True
    recommendation.save()
    
    # Award points for completing a recommendation
    PointsTransaction.objects.create(
        user=request.user,
        points=10,
        transaction_type='earned',
        description=f"Completed recommendation: {recommendation.title}"
    )
    
    return redirect('analytics:dashboard')


@login_required
def rate_content_difficulty(request):
    """
    AJAX endpoint for users to rate content difficulty.
    """
    if request.method == 'POST':
        content_type = request.POST.get('content_type')
        content_id = request.POST.get('content_id')
        rating = int(request.POST.get('rating'))
        
        if content_type and content_id and 1 <= rating <= 5:
            # Get or create content difficulty record
            content_difficulty, created = ContentDifficulty.objects.get_or_create(
                content_type=content_type,
                content_id=content_id,
                defaults={'difficulty_score': rating, 'rating_count': 1}
            )
            
            if not created:
                # Check if user has already rated this content
                existing_rating = UserContentDifficultyRating.objects.filter(
                    user=request.user,
                    content_difficulty=content_difficulty
                ).first()
                
                if existing_rating:
                    # Update existing rating
                    old_rating = existing_rating.rating
                    existing_rating.rating = rating
                    existing_rating.save()
                    
                    # Update content difficulty score
                    total_score = (content_difficulty.difficulty_score * content_difficulty.rating_count) - old_rating + rating
                    content_difficulty.difficulty_score = total_score / content_difficulty.rating_count
                    content_difficulty.save()
                else:
                    # Add new rating
                    UserContentDifficultyRating.objects.create(
                        user=request.user,
                        content_difficulty=content_difficulty,
                        rating=rating
                    )
                    
                    # Update content difficulty score
                    total_score = (content_difficulty.difficulty_score * content_difficulty.rating_count) + rating
                    content_difficulty.rating_count += 1
                    content_difficulty.difficulty_score = total_score / content_difficulty.rating_count
                    content_difficulty.save()
            
            return JsonResponse({'success': True, 'new_score': content_difficulty.difficulty_score})
        
        return JsonResponse({'success': False, 'error': 'Invalid rating parameters'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


class InstructorDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Dashboard for instructors to view analytics about their courses.
    """
    template_name = 'analytics/instructor_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_instructor() or self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get courses taught by this instructor
        courses = Course.objects.filter(instructor=user)
        
        # Get enrollment stats
        enrollment_stats = []
        for course in courses:
            enrollments = Enrollment.objects.filter(course=course)
            total_enrollments = enrollments.count()
            completed = enrollments.filter(status='completed').count()
            dropped = enrollments.filter(status='dropped').count()
            
            # Calculate average progress
            progress_records = Progress.objects.filter(course=course)
            if progress_records.exists():
                avg_progress = progress_records.aggregate(avg=Avg('completion_percentage'))['avg'] or 0
            else:
                avg_progress = 0
            
            # Calculate quiz performance
            course_quizzes = QuizAttempt.objects.filter(quiz__module__course=course)
            avg_quiz_score = course_quizzes.aggregate(avg=Avg('score'))['avg'] or 0
            pass_rate = course_quizzes.filter(passed=True).count() / course_quizzes.count() if course_quizzes.count() > 0 else 0
            
            enrollment_stats.append({
                'course': course,
                'total_enrollments': total_enrollments,
                'completed': completed,
                'dropped': dropped,
                'avg_progress': avg_progress,
                'avg_quiz_score': avg_quiz_score,
                'pass_rate': pass_rate,
            })
        
        context['enrollment_stats'] = enrollment_stats
        context['courses'] = courses
        
        return context


class CourseAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Detailed analytics for a specific course.
    """
    template_name = 'analytics/course_analytics.html'
    context_object_name = 'course'
    
    def test_func(self):
        return self.request.user.is_instructor() or self.request.user.is_staff
    
    def get_queryset(self):
        return Course.objects.filter(instructor=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        
        # Get enrollment data
        enrollments = Enrollment.objects.filter(course=course)
        enrollment_count = enrollments.count()
        completion_count = enrollments.filter(status='completed').count()
        
        # Get progress data
        progress_records = Progress.objects.filter(course=course)
        
        # Get module completion data
        module_data = []
        for module in course.modules.all():
            module_progress = progress_records.filter(module=module)
            completion_percentage = module_progress.aggregate(avg=Avg('completion_percentage'))['avg'] or 0
            
            module_data.append({
                'module': module,
                'completion_percentage': completion_percentage,
            })
        
        # Get quiz performance data
        quiz_data = []
        for module in course.modules.all():
            for quiz in module.contents.filter(quiz__isnull=False):
                quiz_attempts = QuizAttempt.objects.filter(quiz=quiz.quiz)
                avg_score = quiz_attempts.aggregate(avg=Avg('score'))['avg'] or 0
                pass_rate = quiz_attempts.filter(passed=True).count() / quiz_attempts.count() if quiz_attempts.count() > 0 else 0
                
                quiz_data.append({
                    'quiz': quiz.quiz,
                    'attempts': quiz_attempts.count(),
                    'avg_score': avg_score,
                    'pass_rate': pass_rate,
                })
        
        # Get content difficulty ratings
        difficulty_data = []
        for module in course.modules.all():
            for content in module.contents.all():
                if hasattr(content, 'lesson'):
                    content_type = 'lesson'
                    content_id = content.lesson.id
                elif hasattr(content, 'video'):
                    content_type = 'video'
                    content_id = content.video.id
                elif hasattr(content, 'quiz'):
                    content_type = 'quiz'
                    content_id = content.quiz.id
                else:
                    continue
                
                difficulty = ContentDifficulty.objects.filter(
                    content_type=content_type,
                    content_id=content_id
                ).first()
                
                if difficulty:
                    difficulty_data.append({
                        'content': content,
                        'difficulty_score': difficulty.difficulty_score,
                        'rating_count': difficulty.rating_count,
                    })
        
        context.update({
            'enrollment_count': enrollment_count,
            'completion_count': completion_count,
            'completion_rate': (completion_count / enrollment_count * 100) if enrollment_count > 0 else 0,
            'module_data': module_data,
            'quiz_data': quiz_data,
            'difficulty_data': difficulty_data,
        })
        
        return context


@login_required
def log_activity(request):
    """
    AJAX endpoint to log user activity.
    """
    if request.method == 'POST':
        activity_type = request.POST.get('activity_type')
        details = request.POST.get('details', '{}')
        
        if activity_type:
            try:
                details_dict = json.loads(details)
                
                # Create activity record
                UserActivity.objects.create(
                    user=request.user,
                    activity_type=activity_type,
                    content_type=ContentType.objects.get_for_model(course),
                    object_id=course.id
                )
                
                # Update user's last activity date for streak tracking
                request.user.last_activity_date = timezone.now().date()
                request.user.save(update_fields=['last_activity_date'])
                
                # Update streak if applicable
                from gamification.models import Streak
                streak, created = Streak.objects.get_or_create(user=request.user)
                streak.update_streak()
                
                return JsonResponse({'success': True})
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON in details'})
        
        return JsonResponse({'success': False, 'error': 'Activity type is required'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def student_analytics_dashboard(request):
    """
    Display analytics dashboard for students.
    """
    user = request.user
    
    # Get recent activities
    recent_activities = UserActivity.objects.filter(user=user).order_by('-timestamp')[:10]
    
    # Get learning progress
    enrollments = Enrollment.objects.filter(student=user).select_related('course')
    
    # Get quiz performance
    quiz_attempts = QuizAttempt.objects.filter(user=user)
    avg_score = quiz_attempts.aggregate(avg=Avg('score'))['avg'] or 0
    recent_quizzes = quiz_attempts.order_by('-completed_at')[:5]
    
    # Get user performance metrics
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    performance = UserPerformance.objects.filter(
        user=user,
        date__gte=thirty_days_ago
    ).order_by('date')
    
    # Get user badges and achievements
    badges = UserBadge.objects.filter(user=user).select_related('badge')
    achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
    
    # Get personalized recommendations
    recommendations = get_personalized_course_recommendations(user)
    
    # Get areas for improvement
    weak_areas = identify_weak_areas(user)
    
    # Get learning insights
    insights = LearningInsight.objects.filter(user=user, is_read=False).order_by('-generated_at')[:3]
    
    # If no insights exist, generate some
    if not insights.exists() and settings.OPENAI_API_KEY:
        try:
            # Generate insights using OpenAI
            new_insights = generate_learning_insights(user, insight_count=3)
            insights = new_insights
        except Exception as e:
            # Log error but continue with the view
            print(f"Error generating insights: {str(e)}")
    
    context = {
        'recent_activities': recent_activities,
        'enrollments': enrollments,
        'avg_score': avg_score,
        'recent_quizzes': recent_quizzes,
        'performance': performance,
        'badges': badges,
        'achievements': achievements,
        'recommendations': recommendations,
        'weak_areas': weak_areas,
        'insights': insights,
    }
    
    return render(request, 'analytics/student_dashboard.html', context)


@login_required
def instructor_analytics_dashboard(request):
    """
    Display analytics dashboard for instructors with course and student insights.
    """
    user = request.user
    
    if not user.is_instructor:
        return redirect('accounts:dashboard')
    
    # Get instructor's courses
    instructor_courses = Course.objects.filter(instructor=user)
    
    # Get enrollment data
    course_enrollments = []
    for course in instructor_courses:
        enrollments = course.enrollments.count()
        course_enrollments.append({
            'course': course,
            'enrollments': enrollments,
            'completion_rate': calculate_completion_rate(course),
            'avg_rating': course.rating_set.aggregate(Avg('rating'))['rating__avg'] or 0,
        })
    
    # Get quiz performance data across all courses
    quiz_performance = []
    for course in instructor_courses:
        quizzes = Quiz.objects.filter(module__course=course)
        for quiz in quizzes:
            attempts = QuizAttempt.objects.filter(quiz=quiz)
            if attempts.exists():
                avg_score = attempts.aggregate(Avg('score'))['score__avg'] or 0
                quiz_performance.append({
                    'quiz': quiz,
                    'course': course,
                    'avg_score': avg_score,
                    'attempts': attempts.count(),
                })
    
    # Get student engagement data
    student_engagement = analyze_student_engagement(instructor_courses)
    
    # Get badge data for students in instructor's courses
    from django.db.models import Count
    
    # Get all students enrolled in this instructor's courses
    enrolled_students = User.objects.filter(
        enrollments__course__in=instructor_courses
    ).distinct()
    
    # Get badge statistics
    badge_stats = Badge.objects.filter(
        userbadge__user__in=enrolled_students
    ).annotate(
        award_count=Count('userbadge')
    ).order_by('-award_count')[:10]  # Top 10 badges
    
    # Get recent badge awards
    recent_badge_awards = UserBadge.objects.filter(
        user__in=enrolled_students
    ).select_related('user', 'badge').order_by('-earned_at')[:20]
    
    context = {
        'course_enrollments': course_enrollments,
        'quiz_performance': quiz_performance,
        'student_engagement': student_engagement,
        'badge_stats': badge_stats,
        'recent_badge_awards': recent_badge_awards,
        'enrolled_students_count': enrolled_students.count()
    }
    
    return render(request, 'analytics/instructor_dashboard.html', context)


def get_personalized_course_recommendations(user, limit=5):
    """
    Generate personalized course recommendations based on user's performance and interests.
    """
    # Get courses the user is already enrolled in - changed from enrollment__student to enrollments__student
    enrolled_courses = Course.objects.filter(enrollments__student=user)
    
    # Get user's quiz performance to identify strengths and weaknesses
    quiz_attempts = QuizAttempt.objects.filter(user=user)
    
    # If user has no quiz attempts, recommend popular courses
    if not quiz_attempts.exists():
        return Course.objects.exclude(id__in=enrolled_courses).annotate(
            enrollment_count=Count('enrollments')
        ).order_by('-enrollment_count')[:limit]
    
    # Identify topics the user performs well in
    strong_topics = []
    weak_topics = []
    
    for attempt in quiz_attempts:
        quiz = attempt.quiz
        if attempt.score >= 80:  # User is strong in this topic
            strong_topics.append(quiz.module.title)
        elif attempt.score <= 50:  # User is weak in this topic
            weak_topics.append(quiz.module.title)
    
    # Count occurrences of each topic
    strong_topic_counts = Counter(strong_topics)
    weak_topic_counts = Counter(weak_topics)
    
    # Get most common strong and weak topics
    most_common_strong = [topic for topic, _ in strong_topic_counts.most_common(3)]
    most_common_weak = [topic for topic, _ in weak_topic_counts.most_common(3)]
    
    # Recommend courses that cover user's weak topics (for improvement)
    # and are related to user's strong topics (for interest)
    recommended_courses = Course.objects.exclude(id__in=enrolled_courses).filter(
        Q(modules__title__in=most_common_weak) | 
        Q(modules__title__in=most_common_strong)
    ).distinct()
    
    # If not enough recommendations, add popular courses
    if recommended_courses.count() < limit:
        popular_courses = Course.objects.exclude(
            id__in=enrolled_courses
        ).exclude(
            id__in=recommended_courses
        ).annotate(
            enrollment_count=Count('enrollments')
        ).order_by('-enrollment_count')
        
        # Combine the recommendations
        recommended_courses = list(recommended_courses) + list(popular_courses)
        
    return recommended_courses[:limit]


def identify_weak_areas(user):
    """
    Identify areas where the user needs improvement based on quiz performance.
    """
    # Get user's quiz attempts
    quiz_attempts = QuizAttempt.objects.filter(user=user)
    
    if not quiz_attempts.exists():
        return []
    
    # Group attempts by module/topic and calculate average score
    topic_scores = {}
    for attempt in quiz_attempts:
        topic = attempt.quiz.module.title
        if topic not in topic_scores:
            topic_scores[topic] = {'total': 0, 'count': 0}
        
        topic_scores[topic]['total'] += attempt.score
        topic_scores[topic]['count'] += 1
    
    # Calculate average score for each topic
    for topic in topic_scores:
        topic_scores[topic]['avg'] = topic_scores[topic]['total'] / topic_scores[topic]['count']
    
    # Identify weak areas (topics with average score below 70%)
    weak_areas = [
        {'topic': topic, 'avg_score': data['avg']} 
        for topic, data in topic_scores.items() 
        if data['avg'] < 70
    ]
    
    # Sort by average score (ascending)
    weak_areas.sort(key=lambda x: x['avg_score'])
    
    return weak_areas


def calculate_completion_rate(course):
    """
    Calculate the completion rate for a course.
    """
    enrollments = course.enrollments.count()
    if enrollments == 0:
        return 0
    
    completed = course.enrollments.filter(completed=True).count()
    return (completed / enrollments) * 100


def analyze_student_engagement(courses):
    """
    Analyze student engagement across multiple courses.
    """
    engagement_data = []
    
    for course in courses:
        # Get all students enrolled in the course
        enrollments = course.enrollments.all()
        
        # Calculate engagement metrics
        total_students = enrollments.count()
        if total_students == 0:
            continue
            
        active_students = enrollments.filter(
            user__analytics_activities__timestamp__gte=timezone.now() - timezone.timedelta(days=7),
            user__analytics_activities__course=course
        ).distinct().count()
        
        completion_percentage = calculate_completion_rate(course)
        
        # Calculate average time spent
        activities = UserActivity.objects.filter(course=course)
        avg_time_spent = activities.aggregate(Avg('time_spent'))['time_spent__avg'] or 0
        
        engagement_data.append({
            'course': course,
            'total_students': total_students,
            'active_students': active_students,
            'active_percentage': (active_students / total_students) * 100 if total_students > 0 else 0,
            'completion_percentage': completion_percentage,
            'avg_time_spent': avg_time_spent,
        })
    
    return engagement_data 