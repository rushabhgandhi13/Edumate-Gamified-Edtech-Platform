from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, UserProfile, UserActivity


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for the CustomUser model."""
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_student', 'is_instructor', 'points', 'level', 'is_staff', 'date_joined')
    list_filter = ('is_student', 'is_instructor', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'bio', 'profile_picture', 'date_of_birth')}),
        (_('User roles'), {'fields': ('is_student', 'is_instructor')}),
        (_('Gamification'), {'fields': ('points', 'level', 'streak_days')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_student', 'is_instructor'),
        }),
    )


class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__username', 'activity_type')
    date_hierarchy = 'timestamp'
    readonly_fields = ('user', 'activity_type', 'timestamp', 'content_type', 'object_id', 'data')


admin.site.register(UserActivity, UserActivityAdmin) 