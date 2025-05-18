from django.db.models.signals import post_save, m2m_changed, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count

from courses.models import Enrollment, Progress, QuizAttempt
from analytics.models import UserActivity
from .models import (
    Badge, UserBadge, Achievement, UserAchievement,
    PointsTransaction, Streak, Leaderboard, UserChallenge
)
from .utils import check_and_award_progress_badges, check_for_badge_eligibility

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_streak(sender, instance, created, **kwargs):
    """
    Create a streak record for new users.
    """
    if created:
        Streak.objects.create(user=instance)
        
        # Create initial leaderboard entry
        Leaderboard.objects.create(user=instance, points=0, rank=0)


@receiver(post_save, sender=PointsTransaction)
def update_user_points(sender, instance, created, **kwargs):
    """
    Update user points when a new transaction is created.
    """
    if created:
        user = instance.user
        # Calculate total points
        total_points = PointsTransaction.objects.filter(user=user).aggregate(Sum('points'))['points__sum'] or 0
        
        # Update user points
        user.points = total_points
        
        # Update user level based on points
        if total_points >= 1000:
            user.level = 5
        elif total_points >= 500:
            user.level = 4
        elif total_points >= 250:
            user.level = 3
        elif total_points >= 100:
            user.level = 2
        else:
            user.level = 1
            
        user.save(update_fields=['points', 'level'])
        
        # Update leaderboard
        leaderboard, created = Leaderboard.objects.get_or_create(user=user)
        leaderboard.points = total_points
        leaderboard.save()
        
        # Check for badge eligibility
        check_for_badge_eligibility(user)


def check_badge_eligibility(user):
    """Check if user is eligible for any badges based on points"""
    user_points = user.points
    user_badges = UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
    
    # Get badges that user doesn't have and is eligible for
    eligible_badges = Badge.objects.filter(
        points_required__lte=user_points
    ).exclude(
        id__in=user_badges
    )
    
    # Award badges
    for badge in eligible_badges:
        UserBadge.objects.create(
            user=user,
            badge=badge
        )
        
        # Create notification or message
        # This could be implemented with a notification system


@receiver(post_save, sender=QuizAttempt)
def check_quiz_achievements(sender, instance, created, **kwargs):
    """
    Check for quiz-related achievements when a quiz is completed.
    """
    if created and instance.passed:
        user = instance.user
        
        # Update streak
        streak, created = Streak.objects.get_or_create(user=user)
        streak.update_streak()
        
        # Check for quiz score achievements
        quiz_achievements = Achievement.objects.filter(
            achievement_type='quiz_score'
        )
        
        for achievement in quiz_achievements:
            # Check if score is perfect (100%) for "Perfect Score" achievement
            if achievement.name == 'Perfect Score' and instance.score_percentage >= 100:
                # Check if already unlocked
                if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
                    # Unlock achievement
                    UserAchievement.objects.create(
                        user=user,
                        achievement=achievement
                    )
                    
                    # Award badge if applicable
                    if hasattr(achievement, 'badge') and achievement.badge:
                        UserBadge.objects.get_or_create(
                            user=user,
                            badge=achievement.badge
                        )
                    
                    # Award points
                    if achievement.points_reward > 0:
                        PointsTransaction.objects.create(
                            user=user,
                            points=achievement.points_reward,
                            transaction_type='bonus',
                            description=f"Achievement unlocked: {achievement.name}"
                        )


@receiver(post_save, sender=Enrollment)
def check_course_enrollment_achievements(sender, instance, created, **kwargs):
    """
    Check for enrollment-related achievements when a user enrolls in a course.
    """
    if not created:
        return
        
    user = instance.student
    
    # Count total enrollments
    enrollment_count = Enrollment.objects.filter(student=user).count()
    
    # Check for enrollment achievements
    enrollment_achievements = Achievement.objects.filter(
        achievement_type='activity',
        description__icontains='enroll'
    )
    
    for achievement in enrollment_achievements:
        # Use a default threshold of 1 for enrollment achievements
        # or check specifically for first enrollment
        if achievement.name == 'First Course Enrollment' and enrollment_count >= 1:
            # Check if already unlocked
            if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
                # Unlock achievement
                UserAchievement.objects.create(
                    user=user,
                    achievement=achievement
                )
                
                # Award badge if applicable
                if hasattr(achievement, 'badge') and achievement.badge:
                    UserBadge.objects.get_or_create(
                        user=user,
                        badge=achievement.badge
                    )
                
                # Award points
                if achievement.points_reward > 0:
                    PointsTransaction.objects.create(
                        user=user,
                        points=achievement.points_reward,
                        transaction_type='bonus',
                        description=f"Achievement unlocked: {achievement.name}"
                    )


@receiver(post_save, sender=Progress)
def check_course_completion_achievements(sender, instance, **kwargs):
    """
    Check for course completion achievements.
    """
    # Calculate course completion percentage
    course_modules = instance.course.modules.count()
    if course_modules == 0:
        return
    
    user_progress = Progress.objects.filter(
        student=instance.student,
        course=instance.course
    )
    
    total_percentage = sum(p.completion_percentage for p in user_progress)
    overall_percentage = total_percentage / course_modules
    
    # If course is completed (100%)
    if overall_percentage >= 100:
        user = instance.student
        
        # Record course completion
        enrollment = Enrollment.objects.get(student=user, course=instance.course)
        enrollment.status = 'completed'
        enrollment.completion_date = timezone.now()
        enrollment.save()
        
        # Count completed courses
        completed_courses = Enrollment.objects.filter(
            student=user,
            status='completed'
        ).count()
        
        # Check for course completion achievements
        completion_achievements = Achievement.objects.filter(
            achievement_type='course_completion'
        )
        
        for achievement in completion_achievements:
            # For 'Course Completer' achievement, threshold is 1
            if achievement.name == 'Course Completer' and completed_courses >= 1:
                # Check if already unlocked
                if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
                    # Unlock achievement
                    UserAchievement.objects.create(
                        user=user,
                        achievement=achievement
                    )
                    
                    # Award badge if applicable
                    if hasattr(achievement, 'badge') and achievement.badge:
                        UserBadge.objects.get_or_create(
                            user=user,
                            badge=achievement.badge
                        )
                    
                    # Award points
                    if achievement.points_reward > 0:
                        PointsTransaction.objects.create(
                            user=user,
                            points=achievement.points_reward,
                            transaction_type='bonus',
                            description=f"Achievement unlocked: {achievement.name}"
                        )


@receiver(post_save, sender=Streak)
def check_streak_achievements(sender, instance, **kwargs):
    """
    Check for streak-related achievements.
    """
    user = instance.user
    
    # Check for streak achievements
    streak_achievements = Achievement.objects.filter(
        achievement_type='streak'
    )
    
    for achievement in streak_achievements:
        # For 'Consistent Learner' achievement, threshold is 3
        if achievement.name == 'Consistent Learner' and instance.current_streak >= 3:
            # Check if already unlocked
            if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
                # Unlock achievement
                UserAchievement.objects.create(
                    user=user,
                    achievement=achievement
                )
                
                # Award badge if applicable
                if hasattr(achievement, 'badge') and achievement.badge:
                    UserBadge.objects.get_or_create(
                        user=user,
                        badge=achievement.badge
                    )
                
                # Award points
                if achievement.points_reward > 0:
                    PointsTransaction.objects.create(
                        user=user,
                        points=achievement.points_reward,
                        transaction_type='bonus',
                        description=f"Achievement unlocked: {achievement.name}"
                    )


@receiver(post_save, sender=UserChallenge)
def check_challenge_completion(sender, instance, **kwargs):
    """Check if a challenge is completed and award points"""
    if instance.status == 'completed' and instance.completed_at is None:
        # Mark as completed
        instance.completed_at = timezone.now()
        instance.save(update_fields=['completed_at'])
        
        # Award points
        PointsTransaction.objects.create(
            user=instance.user,
            points=instance.challenge.points_reward,
            transaction_type='earned',
            description=f"Completed challenge: {instance.challenge.name}"
        )
        
        # Award badge if associated with challenge
        if instance.challenge.badge:
            UserBadge.objects.get_or_create(
                user=instance.user,
                badge=instance.challenge.badge
            )


@receiver(post_save, sender=Leaderboard)
def update_leaderboard_ranks(sender, instance, **kwargs):
    """Update ranks for all users in the leaderboard"""
    # This is a simple implementation that might not be efficient for large user bases
    # For production, consider using a scheduled task or more efficient approach
    leaderboards = Leaderboard.objects.all().order_by('-points')
    
    for i, leaderboard in enumerate(leaderboards, 1):
        if leaderboard.rank != i:
            leaderboard.rank = i
            leaderboard.save(update_fields=['rank'])


@receiver(post_save, sender=Progress)
def check_badges_on_progress(sender, instance, created, **kwargs):
    """Check for badge eligibility when a user makes progress in a course"""
    if instance.student:
        check_and_award_progress_badges(instance.student)


@receiver(post_save, sender=QuizAttempt)
def check_badges_on_quiz_attempt(sender, instance, created, **kwargs):
    """Check for badge eligibility when a user completes a quiz"""
    # Process for both new quiz attempts and updates to existing attempts where completion status changes
    if instance.user and instance.completed:
        check_and_award_progress_badges(instance.user)


@receiver(post_save, sender=Enrollment)
def check_badges_on_enrollment(sender, instance, created, **kwargs):
    """Check for badge eligibility when a user's enrollment status changes"""
    if instance.student and instance.status == 'completed':
        check_and_award_progress_badges(instance.student)


@receiver(post_save, sender=PointsTransaction)
def check_badges_on_points(sender, instance, created, **kwargs):
    """Check for badge eligibility when a user earns points"""
    if created and instance.user and instance.transaction_type in ['earned', 'bonus']:
        check_for_badge_eligibility(instance.user)


@receiver(post_save, sender=UserActivity)
def check_badges_on_activity(sender, instance, created, **kwargs):
    """Check for badge eligibility when a user is active"""
    if created and instance.user:
        # Only check for activity-based badges once per day per user
        last_check = getattr(instance.user, '_last_activity_badge_check', None)
        today = timezone.now().date()
        
        if not last_check or last_check != today:
            check_and_award_progress_badges(instance.user)
            instance.user._last_activity_badge_check = today


@receiver(post_save, sender=QuizAttempt)
def award_quiz_completion_badges(sender, instance, **kwargs):
    """
    Award badges for quiz completion and performance.
    """
    # Only process when a quiz is completed
    if instance.completed:
        user = instance.user
        
        # Log what's happening (for debugging)
        print(f"Processing quiz {instance.quiz.title} completion for {user.username}")
        print(f"Quiz score: {instance.score_percentage}%, Completed: {instance.completed}, Passed: {instance.passed}")
        
        # Check for first quiz completion badge
        first_quiz_badge = Badge.objects.filter(name='First Quiz Completed').first()
        if first_quiz_badge:
            # Only award if they don't already have this badge
            if not UserBadge.objects.filter(user=user, badge=first_quiz_badge).exists():
                print(f"Awarding First Quiz Completed badge to {user.username}")
                UserBadge.objects.create(
                    user=user,
                    badge=first_quiz_badge
                )
                
                # Award points
                if first_quiz_badge.points_required > 0:
                    PointsTransaction.objects.create(
                        user=user,
                        points=first_quiz_badge.points_required,
                        transaction_type='bonus',
                        description=f"Earned {first_quiz_badge.name} badge"
                    )
        
        # Check for quiz master badge (score above 80%)
        if hasattr(instance, 'score_percentage'):
            score_pct = instance.score_percentage
        else:
            # Calculate if property not available
            score_pct = (instance.score / instance.max_score * 100) if instance.max_score > 0 else 0
            
        if score_pct >= 80:
            quiz_master_badge = Badge.objects.filter(name='Quiz Master').first()
            if quiz_master_badge:
                # Check if user already has this badge
                if not UserBadge.objects.filter(user=user, badge=quiz_master_badge).exists():
                    print(f"Awarding Quiz Master badge to {user.username}")
                    UserBadge.objects.create(
                        user=user,
                        badge=quiz_master_badge
                    )
                    
                    # Award points
                    if quiz_master_badge.points_required > 0:
                        PointsTransaction.objects.create(
                            user=user,
                            points=quiz_master_badge.points_required,
                            transaction_type='bonus',
                            description=f"Earned {quiz_master_badge.name} badge"
                        )
        
        # Also check other progress badges
        check_and_award_progress_badges(user)


@receiver(post_save, sender=Enrollment)
def award_course_completion_badge(sender, instance, **kwargs):
    """
    Award badge when a user completes a course.
    """
    if instance.status == 'completed':
        user = instance.student
        
        # Check for course completion badge
        course_completer_badge = Badge.objects.filter(name='Course Completer').first()
        if course_completer_badge:
            # Check if user already has this badge
            if not UserBadge.objects.filter(user=user, badge=course_completer_badge).exists():
                UserBadge.objects.create(
                    user=user,
                    badge=course_completer_badge
                )
                
                # Award points
                if course_completer_badge.points_required > 0:
                    PointsTransaction.objects.create(
                        user=user,
                        points=course_completer_badge.points_required,
                        transaction_type='bonus',
                        description=f"Earned {course_completer_badge.name} badge"
                    )
        
        # Also check other progress badges
        check_and_award_progress_badges(user) 