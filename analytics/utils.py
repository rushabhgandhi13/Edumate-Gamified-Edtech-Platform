import json
import openai
import logging
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg, Count, Sum, F, Q
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType

from .models import (
    LearningInsight, UserActivity, UserPerformance,
    LearningStyle, AILearningRecommendation
)
from courses.models import (
    Enrollment, Progress, QuizAttempt, Course,
    Lesson, Quiz, Module
)
from gamification.models import UserAchievement, UserBadge, PointsTransaction

logger = logging.getLogger(__name__)


def get_user_learning_data(user):
    month_before = timezone.now().date() - timedelta(days=30)
    
    quiz_results = QuizAttempt.objects.filter(user=user)
    recent_results = quiz_results.filter(completed_at__date__gte=month_before)
    
    overall_score = quiz_results.aggregate(avg=Avg('score'))['avg'] or 0
    monthly_score = recent_results.aggregate(avg=Avg('score'))['avg'] or 0
    
    quiz_metrics = {
        'overall_avg': overall_score,
        'monthly_avg': monthly_score,
        'attempt_count': quiz_results.count(),
        'recent_attempt_count': recent_results.count(),
        'success_rate': quiz_results.filter(passed=True).count() / max(1, quiz_results.count()) * 100,
        'recent_quiz_details': list(recent_results.values(
            'quiz__title', 'score', 'time_spent', 'passed'
        )[:10]),
    }
    
    student_courses = Enrollment.objects.filter(student=user)
    course_metrics = []
    
    for enrolled in student_courses:
        current_progress = Progress.objects.filter(
            student=user, 
            course=enrolled.course
        )
        
        if current_progress.exists():
            completion_sum = sum(p.completion_percentage for p in current_progress)
            avg_completion = completion_sum / current_progress.count()
            
            monthly_interactions = UserActivity.objects.filter(
                user=user,
                timestamp__date__gte=month_before,
                content_type=ContentType.objects.get_for_model(enrolled.course),
                object_id=enrolled.course.id
            ).count()
            
            course_metrics.append({
                'name': enrolled.course.title,
                'completion': avg_completion,
                'enrollment_status': enrolled.status,
                'start_date': enrolled.enrolled_at.strftime('%Y-%m-%d'),
                'monthly_interactions': monthly_interactions,
            })
    
    user_actions = UserActivity.objects.filter(user=user)
    recent_actions = user_actions.filter(timestamp__date__gte=month_before)
    
    activity_metrics = {
        'lifetime_total': user_actions.count(),
        'monthly_total': recent_actions.count(),
        'activity_breakdown': dict(recent_actions.values('activity_type').annotate(count=Count('id')).values_list('activity_type', 'count')),
        'hourly_pattern': dict(recent_actions.extra({'hour': "EXTRACT(HOUR FROM timestamp)"}).values('hour').annotate(count=Count('id')).values_list('hour', 'count')),
        'weekly_pattern': dict(recent_actions.extra({'day': "EXTRACT(DOW FROM timestamp)"}).values('day').annotate(count=Count('id')).values_list('day', 'count')),
    }
    
    monthly_stats = UserPerformance.objects.filter(
        user=user,
        date__gte=month_before
    ).order_by('date')
    
    performance_metrics = {
        'daily_records': list(monthly_stats.values(
            'date', 'quiz_average_score', 'time_spent_minutes', 'content_completed_count', 'points_earned'
        )),
        'study_hours': monthly_stats.aggregate(total=Sum('time_spent_minutes'))['total'] or 0,
        'items_completed': monthly_stats.aggregate(total=Sum('content_completed_count'))['total'] or 0,
    }
    
    gamification_metrics = {
        'lifetime_points': user.points if hasattr(user, 'points') else PointsTransaction.objects.filter(
            user=user, 
            transaction_type__in=['earned', 'bonus']
        ).aggregate(total=Sum('points'))['total'] or 0,
        'achievement_count': UserAchievement.objects.filter(user=user).count(),
        'badge_count': UserBadge.objects.filter(user=user).count(),
        'monthly_points': PointsTransaction.objects.filter(
            user=user,
            timestamp__date__gte=month_before
        ).aggregate(total=Sum('points'))['total'] or 0,
    }
    
    try:
        learner_style = LearningStyle.objects.get(user=user)
        style_metrics = {
            'main_style': learner_style.get_primary_style_display(),
            'backup_style': learner_style.get_secondary_style_display() if learner_style.secondary_style else None,
            'learning_speed': learner_style.get_pace_preference_display(),
            'social_learning': learner_style.prefers_group_learning,
            'practical_focus': learner_style.prefers_practical_examples,
            'theoretical_focus': learner_style.prefers_theory_first,
            'focus_duration': learner_style.attention_span_minutes,
            'self_efficacy': learner_style.confidence_level,
        }
    except LearningStyle.DoesNotExist:
        style_metrics = None
    
    return {
        'user_id': user.id,
        'username': user.username,
        'quiz_metrics': quiz_metrics,
        'course_metrics': course_metrics,
        'activity_metrics': activity_metrics,
        'performance_metrics': performance_metrics,
        'gamification_metrics': gamification_metrics,
        'learning_style': style_metrics,
        'analysis_time': timezone.now().isoformat(),
    }


def generate_learning_insights(user, insight_count=3):
    try:
        logger.info(f"Generating learning insights for user {user.username} (ID: {user.id})")
        
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI API key is not configured")
            raise ValueError("OpenAI API key not configured")
            
        ai_service = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        learner_profile = get_user_learning_data(user)
        
        logger.debug(f"User data gathered for insights generation")
        
        insight_query = f"""Evaluate this student profile and create {insight_count} personalized learning insights. 
        For each insight, include a category, concise title, and detailed explanation.
        
        Student data profile: {json.dumps(learner_profile)}
        
        Structure your response as a JSON array containing:
        - insight_type (choose from: learning_pattern, engagement, performance, strength, weakness, learning_style, improvement)
        - title (brief, descriptive heading)
        - description (thorough explanation with supporting evidence and actionable advice)
        - confidence (numerical value from 0.0 to 1.0)
        
        Prioritize insights that provide substantial, actionable guidance for academic improvement.
        """
        
        logger.info("Sending request to OpenAI API")
        ai_response = ai_service.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an education analytics specialist focused on personalized learning."},
                {"role": "user", "content": insight_query}
            ],
            temperature=0.75,
        )
        
        insight_results = json.loads(ai_response.choices[0].message.content)
        logger.info(f"Received {len(insight_results)} insights from OpenAI")
        
        created_insights = []
        for insight_item in insight_results:
            new_insight = LearningInsight.objects.create(
                user=user,
                title=insight_item['title'],
                description=insight_item['description'],
                insight_type=insight_item['insight_type'],
                relevance_score=insight_item.get('confidence', 0.7)
            )
            created_insights.append(new_insight)
            logger.debug(f"Created insight: {new_insight.title} ({new_insight.insight_type})")
        
        return created_insights
        
    except Exception as err:
        logger.exception(f"Error generating insights for user {user.id}: {str(err)}")
        
        # Create a fallback insight
        fallback_insight = LearningInsight.objects.create(
            user=user,
            title="Study Consistency Recommendation",
            description="Regular, scheduled study sessions have been shown to significantly improve information retention. Consider establishing a consistent daily routine to maximize your learning effectiveness.",
            insight_type='recommendation',
            relevance_score=0.5
        )
        logger.info(f"Created fallback insight for user {user.id}")
        
        return [fallback_insight]


def generate_learning_recommendations(user, count=3):
    try:
        logger.info(f"Generating learning recommendations for user {user.username} (ID: {user.id})")
        
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI API key is not configured")
            raise ValueError("OpenAI API key not configured")
        
        ai_processor = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        learner_data = get_user_learning_data(user)
        
        current_courses = Enrollment.objects.filter(student=user).values_list('course_id', flat=True)
        potential_courses = Course.objects.exclude(id__in=current_courses)[:5]
        
        logger.debug(f"Found {potential_courses.count()} potential courses for recommendations")
        
        course_options = [
            {
                'id': course.id,
                'name': course.title,
                'summary': course.description,
                'level': course.difficulty,
            }
            for course in potential_courses
        ]
        
        recommendation_prompt = f"""Review this student's learning profile and develop {count} tailored educational recommendations. 
        
        Learner profile: {json.dumps(learner_data)}
        
        Available courses: {json.dumps(course_options)}
        
        Structure your response as a JSON array with these fields:
        - recommendation_type (select from: course, resource, study_technique, content_format, practice, challenge, learning_path)
        - title (clear, concise heading)
        - description (explanation of how this recommendation addresses the student's specific needs)
        - priority (low, medium, high)
        - confidence (numerical value from 0.0 to 1.0)
        - course_id (include only for course-type recommendations)
        
        Each recommendation should directly address the student's observed learning patterns and improvement opportunities.
        """
        
        logger.info("Sending recommendation request to OpenAI API")
        ai_result = ai_processor.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a learning pathway advisor creating personalized educational journeys."},
                {"role": "user", "content": recommendation_prompt}
            ],
            temperature=0.72,
        )
        
        recommendation_data = json.loads(ai_result.choices[0].message.content)
        logger.info(f"Received {len(recommendation_data)} recommendations from OpenAI")
        
        stored_recommendations = []
        for rec_item in recommendation_data:
            recommendation = AILearningRecommendation(
                user=user,
                title=rec_item['title'],
                description=rec_item['description'],
                recommendation_type=rec_item['recommendation_type'],
                urgency=rec_item.get('priority', 'medium'),
                confidence_score=rec_item.get('confidence', 0.7),
                expires_at=timezone.now() + timedelta(days=28)
            )
            
            if 'course_id' in rec_item and rec_item['recommendation_type'] == 'course':
                try:
                    recommended_course = Course.objects.get(id=rec_item['course_id'])
                    recommendation.content_type = ContentType.objects.get_for_model(Course)
                    recommendation.object_id = recommended_course.id
                    logger.debug(f"Linking recommendation to course ID: {recommended_course.id}")
                except Course.DoesNotExist:
                    logger.warning(f"Course ID {rec_item['course_id']} does not exist")
                    pass
            
            recommendation.save()
            stored_recommendations.append(recommendation)
            logger.debug(f"Created recommendation: {recommendation.title}")
            
        return stored_recommendations
        
    except Exception as e:
        logger.exception(f"Error generating recommendations for user {user.id}: {str(e)}")
        
        default_recommendation = AILearningRecommendation.objects.create(
            user=user,
            title="Enhanced Study Techniques",
            description="Based on your recent activity, you might benefit from incorporating spaced repetition techniques into your study routine. This approach can help improve long-term retention of key concepts.",
            recommendation_type="study_technique",
            urgency="medium",
            confidence_score=0.6,
            expires_at=timezone.now() + timedelta(days=14)
        )
        logger.info(f"Created fallback recommendation for user {user.id}")
        
        return [default_recommendation]


def detect_learning_style(user):
    user_behaviors = UserActivity.objects.filter(user=user)
    
    visual_interactions = user_behaviors.filter(
        Q(activity_type='video_view') | 
        Q(activity_type='image_view')
    ).count()
    
    audio_interactions = user_behaviors.filter(
        Q(activity_type='audio_view') | 
        Q(activity_type='video_view')
    ).count()
    
    text_interactions = user_behaviors.filter(
        Q(activity_type='lesson_view') | 
        Q(activity_type='document_view') |
        Q(activity_type='article_view')
    ).count()
    
    interactive_interactions = user_behaviors.filter(
        Q(activity_type='quiz_attempt') |
        Q(activity_type='interactive_activity')
    ).count()
    
    interaction_types = {
        'visual': visual_interactions,
        'auditory': audio_interactions,
        'reading': text_interactions,
        'kinesthetic': interactive_interactions
    }
    
    if sum(interaction_types.values()) < 10:
        return None
    
    sorted_types = sorted(interaction_types.items(), key=lambda x: x[1], reverse=True)
    
    primary_preference = sorted_types[0][0]
    secondary_preference = sorted_types[1][0] if sorted_types[1][1] > 0 else None
    
    if len(sorted_types) >= 2:
        top_value = sorted_types[0][1]
        runner_up = sorted_types[1][1]
        if top_value > 0 and runner_up / top_value >= 0.8:
            primary_preference = 'multimodal'
            secondary_preference = f"{sorted_types[0][0]}-{sorted_types[1][0]}"
    
    recent_performance = UserPerformance.objects.filter(user=user).order_by('-date')[:30]
    
    if recent_performance.exists():
        avg_study_time = recent_performance.aggregate(avg=Avg('time_spent_minutes'))['avg'] or 0
        material_completed = recent_performance.aggregate(sum=Sum('content_completed_count'))['sum'] or 0
        
        time_per_material = avg_study_time / max(1, material_completed)
        
        if time_per_material < 5:
            pace_style = 'fast'
        elif time_per_material > 15:
            pace_style = 'slow'
        else:
            pace_style = 'moderate'
    else:
        pace_style = 'moderate'
    
    social_preference = user_behaviors.filter(
        Q(activity_type='forum_post') | 
        Q(activity_type='comment') |
        Q(activity_type='discussion')
    ).count() > 5
    
    learner_style, created = LearningStyle.objects.update_or_create(
        user=user,
        defaults={
            'primary_style': primary_preference,
            'secondary_style': secondary_preference,
            'pace_preference': pace_style,
            'prefers_group_learning': social_preference,
            'prefers_practical_examples': True,
            'prefers_theory_first': False,
            'attention_span_minutes': 30,
            'confidence_level': 3
        }
    )
    
    return learner_style 