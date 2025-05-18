from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model, login, authenticate
from django.urls import reverse_lazy, reverse
from django.views.generic import UpdateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Count, Sum

from .models import UserProfile
from courses.models import Course, Enrollment
from analytics.models import UserActivity
from .forms import (
    CustomUserChangeForm, UserProfileForm, UserRegistrationForm, 
    UserUpdateForm, ProfileUpdateForm, SignUpForm, ProfileForm
)
from gamification.models import UserAchievement, UserBadge

User = get_user_model()


def register(request):
    """
    Register a new user.
    """
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Account created for {user.username}! You can now log in.')
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    """
    User dashboard showing enrolled courses, achievements, and activity.
    """
    user = request.user
    
    # Get enrolled courses
    enrollments = Enrollment.objects.filter(student=user).select_related('course')[:4]
    
    # Calculate progress for each course
    for enrollment in enrollments:
        course = enrollment.course
        progress_records = user.progress.filter(course=course)
        
        if progress_records.exists():
            total_percentage = sum(p.completion_percentage for p in progress_records)
            enrollment.overall_progress = total_percentage / progress_records.count()
        else:
            enrollment.overall_progress = 0
    
    # Get recent activities
    recent_activities = UserActivity.objects.filter(user=user).order_by('-timestamp')[:5]
    
    # Get achievements and badges - using date_earned instead of unlocked_at
    achievements = UserAchievement.objects.filter(user=user).select_related('achievement').order_by('-date_earned')[:3]
    badges = UserBadge.objects.filter(user=user).select_related('badge').order_by('-earned_at')[:3]
    
    context = {
        'enrollments': enrollments,
        'recent_activities': recent_activities,
        'achievements': achievements,
        'badges': badges,
    }
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_detail(request, username):
    """
    Display a user's profile
    """
    user = get_object_or_404(User, username=username)
    return render(request, 'accounts/profile_detail.html', {'profile_user': user})


@login_required
def profile_update(request):
    """
    Allow a user to update their profile
    """
    if request.method == 'POST':
        user_form = CustomUserChangeForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('accounts:profile')
    else:
        user_form = CustomUserChangeForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user.profile)
    
    return render(request, 'accounts/profile_update.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


class LeaderboardView(ListView):
    """
    View for displaying the leaderboard of users based on points.
    """
    model = User
    template_name = 'accounts/leaderboard.html'
    context_object_name = 'users'
    
    def get_queryset(self):
        return User.objects.filter(is_active=True).order_by('-points')[:50]


def signup(request):
    """
    View for user registration
    """
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in after signup
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=user.username, password=raw_password)
            login(request, user)
            messages.success(request, "Your account has been created successfully!")
            return redirect('home')
    else:
        form = SignUpForm()
    
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def profile(request):
    """
    View for displaying user profile
    """
    return render(request, 'accounts/profile.html')


@login_required
def edit_profile(request):
    """
    View for editing user profile
    """
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('accounts:profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def become_student(request):
    """
    Allow a user to become a student.
    """
    user = request.user
    
    if not user.is_student:
        user.is_student = True
        user.save()
        messages.success(request, 'You are now registered as a student!')
    else:
        messages.info(request, 'You are already registered as a student.')
    
    return redirect('accounts:dashboard')


@login_required
def become_instructor(request):
    """
    Allow a user to become an instructor.
    """
    user = request.user
    
    if not user.is_instructor:
        user.is_instructor = True
        user.save()
        messages.success(request, 'You are now registered as an instructor!')
    else:
        messages.info(request, 'You are already registered as an instructor.')
    
    return redirect('accounts:dashboard') 