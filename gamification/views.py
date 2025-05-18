from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Count, Sum
from django.http import JsonResponse

from .models import (
    Badge, UserBadge, Achievement, UserAchievement,
    Challenge, UserChallenge, PointsTransaction, Streak, Point, ProgressBadge, Leaderboard
)
from accounts.models import CustomUser
from .utils import check_and_award_progress_badges, check_for_badge_eligibility


@login_required
def achievements_view(request):
    """
    Display user's achievements and badges.
    """
    user = request.user
    
    # Check for new badges first
    check_and_award_progress_badges(user)
    check_for_badge_eligibility(user)
    
    # Get user's achievements
    user_achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
    
    # Get user's badges
    user_badges = UserBadge.objects.filter(user=user).select_related('badge')
    
    # Get all available achievements
    all_achievements = Achievement.objects.all()
    
    # Calculate progress for each achievement
    for achievement in all_achievements:
        if any(ua.achievement.id == achievement.id for ua in user_achievements):
            achievement.unlocked = True
            achievement.progress = 100
        else:
            achievement.unlocked = False
            
            # Calculate progress based on achievement type
            if achievement.achievement_type == 'points':
                total_points = user.points if hasattr(user, 'points') else 0
                achievement.progress = min(100, int((total_points / 100) * 100))
            elif achievement.achievement_type == 'course_completion':
                from courses.models import Enrollment
                completed_courses = Enrollment.objects.filter(
                    student=user,
                    status='completed'
                ).count()
                # Assume threshold is 1 for course completion
                achievement.progress = min(100, int((completed_courses / 1) * 100))
            elif achievement.achievement_type == 'streak':
                streak = getattr(user, 'streak', None)
                if streak:
                    # Assume threshold is 3 for streak achievements
                    achievement.progress = min(100, int((streak.current_streak / 3) * 100))
                else:
                    achievement.progress = 0
            else:
                achievement.progress = 0
    
    context = {
        'user_achievements': user_achievements,
        'user_badges': user_badges,
        'all_achievements': all_achievements,
    }
    
    return render(request, 'gamification/achievements.html', context)


@login_required
def badges_view(request):
    """
    Display user's badges and available badges.
    """
    user = request.user
    
    # Check for new badges
    new_progress_badges = check_and_award_progress_badges(user)
    new_point_badges = check_for_badge_eligibility(user)
    
    # Show notification if new badges were earned
    new_badges = new_progress_badges + new_point_badges
    if new_badges:
        badge_names = ", ".join([badge.badge.name for badge in new_badges])
        messages.success(request, _(f"Congratulations! You've earned new badges: {badge_names}"))
    
    # Get user's badges
    user_badges = UserBadge.objects.filter(user=user).select_related('badge')
    
    # Get all available badges
    all_badges = Badge.objects.all()
    
    # Mark badges as earned or not
    for badge in all_badges:
        badge.earned = any(ub.badge.id == badge.id for ub in user_badges)
        
        # Add progress information for progress badges
        if hasattr(badge, 'progress_criteria'):
            progress_badge = badge.progress_criteria
            badge.progress_type = progress_badge.get_progress_type_display()
            badge.threshold = progress_badge.threshold
            
            # Calculate progress percentage based on badge type
            if progress_badge.progress_type == 'course_completion':
                from courses.models import Enrollment
                completions = Enrollment.objects.filter(student=user, status='completed').count()
                badge.progress = min(100, int((completions / progress_badge.threshold) * 100))
                
            elif progress_badge.progress_type == 'points_milestone':
                total_points = user.points if hasattr(user, 'points') else PointsTransaction.objects.filter(
                    user=user, 
                    transaction_type__in=['earned', 'bonus']
                ).aggregate(total=Sum('points'))['total'] or 0
                badge.progress = min(100, int((total_points / progress_badge.threshold) * 100))
            
            else:
                # Default progress display
                badge.progress = 0 if not badge.earned else 100
        else:
            badge.progress = 0 if not badge.earned else 100
    
    # Group badges by type
    achievement_badges = [b for b in all_badges if b.badge_type == 'achievement']
    progress_badges = [b for b in all_badges if b.badge_type == 'progress']
    activity_badges = [b for b in all_badges if b.badge_type == 'activity']
    special_badges = [b for b in all_badges if b.badge_type == 'special']
    mastery_badges = [b for b in all_badges if b.badge_type == 'mastery']
    
    context = {
        'user_badges': user_badges,
        'all_badges': all_badges,
        'achievement_badges': achievement_badges,
        'progress_badges': progress_badges,
        'activity_badges': activity_badges,
        'special_badges': special_badges,
        'mastery_badges': mastery_badges,
    }
    
    return render(request, 'gamification/badges.html', context)


@login_required
def challenges_view(request):
    """
    Display active challenges and user's challenge progress.
    """
    user = request.user
    
    # Get active challenges
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )
    
    # Get user's challenges
    user_challenges = UserChallenge.objects.filter(
        user=user
    ).select_related('challenge')
    
    # Create a dictionary of challenge_id -> user_challenge
    user_challenge_dict = {uc.challenge.id: uc for uc in user_challenges}
    
    # Add user progress to active challenges
    for challenge in active_challenges:
        if challenge.id in user_challenge_dict:
            challenge.user_status = user_challenge_dict[challenge.id].status
            challenge.user_progress = user_challenge_dict[challenge.id].progress
        else:
            challenge.user_status = None
            challenge.user_progress = 0
    
    context = {
        'active_challenges': active_challenges,
        'user_challenges': user_challenges,
    }
    
    return render(request, 'gamification/challenges.html', context)


@login_required
def accept_challenge(request, challenge_id):
    """
    Accept a challenge.
    """
    challenge = get_object_or_404(Challenge, id=challenge_id, is_active=True)
    
    # Check if challenge is still active
    if not challenge.is_ongoing:
        messages.error(request, _("This challenge is no longer active."))
        return redirect('gamification:challenges')
    
    # Check if already accepted
    if UserChallenge.objects.filter(user=request.user, challenge=challenge).exists():
        messages.info(request, _("You have already accepted this challenge."))
    else:
        # Create user challenge
        UserChallenge.objects.create(
            user=request.user,
            challenge=challenge,
            status='accepted'
        )
        messages.success(request, _("Challenge accepted! Complete it before it expires to earn rewards."))
    
    return redirect('gamification:challenges')


@login_required
def points_history(request):
    """
    Display user's points transaction history.
    """
    user = request.user
    
    # Get points transactions
    transactions = PointsTransaction.objects.filter(user=user).order_by('-timestamp')
    
    # Calculate points by category
    points_by_category = {}
    for transaction in transactions:
        category = transaction.transaction_type
        points = transaction.points
        
        if category not in points_by_category:
            points_by_category[category] = 0
        
        if category in ['earned', 'bonus']:
            points_by_category[category] += points
        elif category in ['spent', 'penalty']:
            points_by_category[category] -= points
    
    context = {
        'transactions': transactions,
        'points_by_category': points_by_category,
    }
    
    return render(request, 'gamification/points_history.html', context)


@login_required
def leaderboard(request):
    """
    Display the leaderboard of users ranked by points.
    """
    # Get top leaderboard entries
    top_leaders = Leaderboard.objects.select_related('user').order_by('rank')[:20]  # Top 20 users
    
    # Get current user's rank
    user_leaderboard = None
    if request.user.is_authenticated:
        try:
            user_leaderboard = Leaderboard.objects.get(user=request.user)
        except Leaderboard.DoesNotExist:
            pass
    
    # Get users with most badges - remove the is_student filter
    badge_leaders = CustomUser.objects.annotate(
        badge_count=Count('badges')
    ).filter(badge_count__gt=0).order_by('-badge_count')[:10]  # Top 10 users with badges
    
    # Get users with longest streaks
    streak_leaders = Streak.objects.filter(current_streak__gt=0).order_by('-current_streak')[:10]
    
    context = {
        'top_leaders': top_leaders,
        'user_leaderboard': user_leaderboard,
        'badge_leaders': badge_leaders,
        'streak_leaders': streak_leaders,
    }
    
    return render(request, 'gamification/leaderboard.html', context)


@login_required
def update_streak(request):
    """
    AJAX endpoint to update user's streak.
    """
    if request.method == 'POST':
        user = request.user
        
        # Get or create streak
        streak, created = Streak.objects.get_or_create(user=user)
        
        # Update streak
        streak.update_streak()
        
        return JsonResponse({
            'success': True,
            'current_streak': streak.current_streak,
            'longest_streak': streak.longest_streak,
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def achievements(request):
    """
    Display all available achievements and the user's progress.
    """
    all_achievements = Achievement.objects.all()
    user_achievements = request.user.achievement_set.all()
    
    context = {
        'all_achievements': all_achievements,
        'user_achievements': user_achievements,
    }
    
    return render(request, 'gamification/achievements.html', context)


@login_required
def badges(request):
    """
    Display all available badges and the user's earned badges.
    """
    all_badges = Badge.objects.all()
    user_badges = request.user.badge_set.all()
    
    context = {
        'all_badges': all_badges,
        'user_badges': user_badges,
    }
    
    return render(request, 'gamification/badges.html', context) 