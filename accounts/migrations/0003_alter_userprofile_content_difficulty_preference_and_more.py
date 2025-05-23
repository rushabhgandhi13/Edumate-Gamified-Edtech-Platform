# Generated by Django 4.2.7 on 2025-03-15 17:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('accounts', '0002_alter_customuser_options_alter_userprofile_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='content_difficulty_preference',
            field=models.CharField(choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced'), ('all', 'All Levels')], default='all', max_length=20, verbose_name='Content Difficulty Preference'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='social_links',
            field=models.JSONField(blank=True, default=dict, null=True, verbose_name='Social Links'),
        ),
        migrations.CreateModel(
            name='UserActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(choices=[('login', 'Login'), ('logout', 'Logout'), ('course_view', 'Course View'), ('course_enrollment', 'Course Enrollment'), ('module_view', 'Module View'), ('lesson_view', 'Lesson View'), ('quiz_attempt', 'Quiz Attempt'), ('personalized_quiz_attempt', 'Personalized Quiz Attempt'), ('achievement_earned', 'Achievement Earned'), ('profile_update', 'Profile Update'), ('search', 'Search')], max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('data', models.JSONField(blank=True, default=dict, null=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='account_activities', to='contenttypes.contenttype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='account_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Activity',
                'verbose_name_plural': 'User Activities',
                'ordering': ['-timestamp'],
            },
        ),
    ]
