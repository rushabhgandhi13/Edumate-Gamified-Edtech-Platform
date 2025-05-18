from django.contrib import admin
from .models import (
    Point, Badge, Achievement, UserBadge, UserAchievement,
    Challenge, UserChallenge, Streak, PointsTransaction, ProgressBadge
)

@admin.register(Point)
class PointAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'description', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('user__username', 'description')
    date_hierarchy = 'timestamp'

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'badge_type', 'image', 'points_required')
    list_filter = ('badge_type', 'created_at')
    search_fields = ('name', 'description')

@admin.register(ProgressBadge)
class ProgressBadgeAdmin(admin.ModelAdmin):
    list_display = ('badge', 'progress_type', 'threshold', 'difficulty')
    list_filter = ('progress_type', 'difficulty')
    search_fields = ('badge__name',)
    autocomplete_fields = ['badge', 'course', 'module']

@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'points_reward', 'achievement_type')
    search_fields = ('name', 'description')
    list_filter = ('achievement_type',)

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    list_filter = ('badge', 'earned_at')
    search_fields = ('user__username', 'badge__name')
    date_hierarchy = 'earned_at'

@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'date_earned')
    list_filter = ('date_earned', 'achievement')
    search_fields = ('user__username', 'achievement__name')

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('name', 'difficulty', 'points_reward', 'is_active', 'start_date', 'end_date')
    list_filter = ('difficulty', 'is_active', 'start_date')
    search_fields = ('name', 'description')
    date_hierarchy = 'start_date'

@admin.register(UserChallenge)
class UserChallengeAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'status', 'progress', 'completed_at')
    list_filter = ('status', 'challenge')
    search_fields = ('user__username', 'challenge__name')
    date_hierarchy = 'completed_at'

@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_streak', 'longest_streak', 'last_activity_date')
    list_filter = ('last_activity_date',)
    search_fields = ('user__username',)

@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'transaction_type', 'description', 'timestamp')
    list_filter = ('transaction_type', 'timestamp')
    search_fields = ('user__username', 'description')
    date_hierarchy = 'timestamp' 