from django.urls import path
from . import views

app_name = 'gamification'

urlpatterns = [
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('achievements/', views.achievements, name='achievements'),
    path('badges/', views.badges, name='badges'),
    path('challenges/', views.challenges_view, name='challenges'),
    path('challenges/<int:challenge_id>/accept/', views.accept_challenge, name='accept_challenge'),
    path('points-history/', views.points_history, name='points_history'),
    path('update-streak/', views.update_streak, name='update_streak'),
] 