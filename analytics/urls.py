from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('insights/', views.learning_insights, name='learning_insights'),
    path('insights/generate/', views.generate_insight, name='generate_insight'),
    path('recommendations/generate/', views.generate_recommendation, name='generate_recommendation'),
    path('recommendations/<int:recommendation_id>/dismiss/', views.dismiss_recommendation, name='dismiss_recommendation'),
    path('recommendations/<int:recommendation_id>/complete/', views.complete_recommendation, name='complete_recommendation'),
    path('learning-style/', views.learning_style_view, name='learning_style'),
    path('rate-difficulty/', views.rate_content_difficulty, name='rate_difficulty'),
    path('instructor-dashboard/', views.InstructorDashboardView.as_view(), name='instructor_dashboard'),
    path('course-analytics/<slug:slug>/', views.CourseAnalyticsView.as_view(), name='course_analytics'),
    path('log-activity/', views.log_activity, name='log_activity'),
    path('dashboard/student/', views.student_analytics_dashboard, name='student_dashboard'),
    path('dashboard/instructor/', views.instructor_analytics_dashboard, name='instructor_dashboard'),
] 