from django.core.management.base import BaseCommand
from gamification.models import Badge, ProgressBadge

class Command(BaseCommand):
    help = 'Creates default badges for the gamification system'

    def handle(self, *args, **options):
        # Create achievement badges
        self.create_achievement_badges()
        # Create progress badges
        self.create_progress_badges()
        
        self.stdout.write(self.style.SUCCESS('Successfully created default badges'))
    
    def create_achievement_badges(self):
        """Create basic achievement badges"""
        achievement_badges = [
            {
                'name': 'First Quiz Completed',
                'description': 'Completed your first quiz! This is the beginning of your learning journey.',
                'icon': 'fa-check-circle',
                'badge_type': 'achievement',
                'points_required': 10
            },
            {
                'name': 'Course Completer',
                'description': 'Completed a full course! Your dedication to learning is commendable.',
                'icon': 'fa-graduation-cap',
                'badge_type': 'achievement',
                'points_required': 50
            },
            {
                'name': 'Quiz Master',
                'description': 'Scored above 80% in a quiz! Your understanding of the material is exceptional.',
                'icon': 'fa-award',
                'badge_type': 'achievement',
                'points_required': 25
            },
            {
                'name': 'Consistent Learner',
                'description': 'Logged in for 3 consecutive days! Your consistency is key to success.',
                'icon': 'fa-calendar-check',
                'badge_type': 'achievement',
                'points_required': 15
            }
        ]
        
        for badge_data in achievement_badges:
            badge, created = Badge.objects.get_or_create(
                name=badge_data['name'],
                defaults={
                    'description': badge_data['description'],
                    'icon': badge_data['icon'],
                    'badge_type': badge_data['badge_type'],
                    'points_required': badge_data['points_required']
                }
            )
            if created:
                self.stdout.write(f"Created badge: {badge.name}")
            else:
                self.stdout.write(f"Badge already exists: {badge.name}")
    
    def create_progress_badges(self):
        """Create progress-based badges with specific criteria"""
        # First, create the badge objects
        first_quiz_badge, _ = Badge.objects.get_or_create(
            name='First Quiz Completed',
            defaults={
                'description': 'Completed your first quiz!',
                'icon': 'fa-check-circle',
                'badge_type': 'progress',
                'points_required': 10
            }
        )
        
        course_completion_badge, _ = Badge.objects.get_or_create(
            name='Course Completer',
            defaults={
                'description': 'Completed a full course',
                'icon': 'fa-graduation-cap',
                'badge_type': 'progress',
                'points_required': 50
            }
        )
        
        quiz_master_badge, _ = Badge.objects.get_or_create(
            name='Quiz Master',
            defaults={
                'description': 'Scored above 80% in a quiz',
                'icon': 'fa-award',
                'badge_type': 'progress',
                'points_required': 25
            }
        )
        
        consecutive_login_badge, _ = Badge.objects.get_or_create(
            name='Consistent Learner',
            defaults={
                'description': 'Logged in for 3 consecutive days',
                'icon': 'fa-calendar-check',
                'badge_type': 'progress',
                'points_required': 15
            }
        )
        
        # Then create the progress criteria for each badge
        ProgressBadge.objects.get_or_create(
            badge=first_quiz_badge,
            defaults={
                'progress_type': 'quiz_performance',
                'threshold': 1  # Just need to complete 1 quiz
            }
        )
        
        ProgressBadge.objects.get_or_create(
            badge=course_completion_badge,
            defaults={
                'progress_type': 'course_completion',
                'threshold': 1  # Complete 1 course
            }
        )
        
        ProgressBadge.objects.get_or_create(
            badge=quiz_master_badge,
            defaults={
                'progress_type': 'quiz_performance',
                'threshold': 1,  # Complete 1 quiz with this score
                'min_score': 80  # Minimum score of 80%
            }
        )
        
        # For consecutive login, we'll need a different implementation
        # since it's not directly supported by ProgressBadge
        # We'll implement it through the Streak model 