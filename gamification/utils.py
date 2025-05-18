from django.utils import timezone
from django.db.models import Count, Sum, Avg
from .models import Badge, UserBadge, ProgressBadge, PointsTransaction
from courses.models import Progress, QuizAttempt
from analytics.models import UserActivity

def check_and_award_progress_badges(user):
    """
    Check user's progress against all progress badge criteria and award badges accordingly.
    Returns a list of newly awarded badges.
    """
    newly_awarded = []
    all_progress_badges = ProgressBadge.objects.select_related('badge').all()
    
    # Get user's existing badges to avoid rechecking
    user_badge_ids = UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
    
    for progress_badge in all_progress_badges:
        # Skip if user already has this badge
        if progress_badge.badge.id in user_badge_ids:
            continue
            
        badge_earned = False
        
        # Check based on progress type
        if progress_badge.progress_type == 'course_completion':
            # Check if user has completed the specified course or any course
            from courses.models import Enrollment
            
            enrollments = Enrollment.objects.filter(student=user, status='completed')
            if progress_badge.course:
                # Check for specific course
                badge_earned = enrollments.filter(course=progress_badge.course).exists()
            else:
                # Check for course count
                completed_count = enrollments.count()
                badge_earned = completed_count >= progress_badge.threshold
                
        elif progress_badge.progress_type == 'module_completion':
            # Check modules completed
            modules_completed = 0
            
            if progress_badge.course and progress_badge.module:
                # Specific module in specific course
                progress = Progress.objects.filter(
                    student=user,
                    course=progress_badge.course,
                    module=progress_badge.module
                ).first()
                
                if progress and progress.completion_percentage == 100:
                    badge_earned = True
            elif progress_badge.course:
                # All modules in specific course
                progress_records = Progress.objects.filter(
                    student=user,
                    course=progress_badge.course,
                    completion_percentage=100
                )
                modules_completed = progress_records.count()
                badge_earned = modules_completed >= progress_badge.threshold
            else:
                # Any modules
                progress_records = Progress.objects.filter(
                    student=user,
                    completion_percentage=100
                )
                modules_completed = progress_records.count()
                badge_earned = modules_completed >= progress_badge.threshold
                
        elif progress_badge.progress_type == 'lesson_completion':
            # Check lessons completed
            # Since LessonCompletion model doesn't exist, we'll use Progress model to estimate
            # lessons completed based on module completion percentage
            from courses.models import Lesson, Module
            
            lesson_count = 0
            
            if progress_badge.course:
                if progress_badge.module:
                    # Specific module
                    try:
                        # Get lesson count in the module
                        total_lessons = Lesson.objects.filter(
                            module=progress_badge.module
                        ).count()
                        
                        # Get progress for this module
                        progress = Progress.objects.filter(
                            student=user,
                            course=progress_badge.course,
                            module=progress_badge.module
                        ).first()
                        
                        if progress:
                            # Estimate completed lessons based on completion percentage
                            lesson_count = int((progress.completion_percentage / 100) * total_lessons)
                    except:
                        lesson_count = 0
                else:
                    # All modules in course
                    modules = Module.objects.filter(course=progress_badge.course)
                    for module in modules:
                        total_lessons = Lesson.objects.filter(module=module).count()
                        progress = Progress.objects.filter(
                            student=user,
                            course=progress_badge.course,
                            module=module
                        ).first()
                        
                        if progress:
                            lesson_count += int((progress.completion_percentage / 100) * total_lessons)
            else:
                # Any lessons across all courses
                progress_records = Progress.objects.filter(student=user)
                for progress in progress_records:
                    total_lessons = Lesson.objects.filter(module=progress.module).count()
                    lesson_count += int((progress.completion_percentage / 100) * total_lessons)
            
            badge_earned = lesson_count >= progress_badge.threshold
            
        elif progress_badge.progress_type == 'quiz_performance':
            # Check quiz performance
            quiz_attempts = QuizAttempt.objects.filter(user=user, completed=True, passed=True)
            
            if progress_badge.course:
                quiz_attempts = quiz_attempts.filter(quiz__module__course=progress_badge.course)
                
            if progress_badge.module:
                quiz_attempts = quiz_attempts.filter(quiz__module=progress_badge.module)
                
            # Check for score threshold if specified
            if progress_badge.min_score:
                high_scoring_attempts = []
                for attempt in quiz_attempts:
                    # Use score_percentage property if available, otherwise calculate
                    if hasattr(attempt, 'score_percentage'):
                        score_pct = attempt.score_percentage
                    else:
                        score_pct = (attempt.score / attempt.max_score * 100) if attempt.max_score > 0 else 0
                    
                    if score_pct >= progress_badge.min_score:
                        high_scoring_attempts.append(attempt)
                
                badge_earned = len(high_scoring_attempts) >= progress_badge.threshold
            else:
                # Just count the number of passed attempts
                badge_earned = quiz_attempts.count() >= progress_badge.threshold
            
        elif progress_badge.progress_type == 'activity_count':
            # Check activity count
            activities = UserActivity.objects.filter(user=user)
            badge_earned = activities.count() >= progress_badge.threshold
            
        elif progress_badge.progress_type == 'points_milestone':
            # Check points milestone
            total_points = user.points if hasattr(user, 'points') else PointsTransaction.objects.filter(
                user=user, 
                transaction_type__in=['earned', 'bonus']
            ).aggregate(total=Sum('points'))['total'] or 0
            
            badge_earned = total_points >= progress_badge.threshold
        
        # Award badge if criteria met
        if badge_earned:
            user_badge = UserBadge.objects.create(
                user=user,
                badge=progress_badge.badge,
                earned_at=timezone.now()
            )
            
            # Create points transaction for badge
            if progress_badge.badge.points_required > 0:
                PointsTransaction.objects.create(
                    user=user,
                    points=progress_badge.badge.points_required,
                    transaction_type='bonus',
                    description=f"Earned {progress_badge.badge.name} badge"
                )
            
            newly_awarded.append(user_badge)
            
    return newly_awarded


def check_for_badge_eligibility(user):
    """Check if user is eligible for any badges based on points"""
    user_points = user.points if hasattr(user, 'points') else PointsTransaction.objects.filter(
        user=user, 
        transaction_type__in=['earned', 'bonus']
    ).aggregate(total=Sum('points'))['total'] or 0
    
    # Get badges the user doesn't have yet that are point-based
    eligible_badges = Badge.objects.filter(
        points_required__lte=user_points
    ).exclude(
        id__in=UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
    )
    
    # Award the badges
    newly_awarded = []
    for badge in eligible_badges:
        user_badge = UserBadge.objects.create(
            user=user,
            badge=badge,
            earned_at=timezone.now()
        )
        newly_awarded.append(user_badge)
        
    return newly_awarded 