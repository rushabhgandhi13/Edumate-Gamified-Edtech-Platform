from django.core.management.base import BaseCommand
from gamification.models import Badge, PointsTransaction, UserBadge
from courses.models import QuizAttempt
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Checks and fixes badges'

    def handle(self, *args, **options):
        self.stdout.write('Checking badges...')
        
        # Create badges if they don't exist
        self.create_badges()
        
        # Check and award quiz badges
        self.award_quiz_badges()
        
        self.stdout.write(self.style.SUCCESS('Badges have been checked and fixed!'))
    
    def create_badges(self):
        """Create standard badges if they don't exist"""
        badges = [
            {
                'name': 'First Quiz Completed',
                'description': 'Completed your first quiz',
                'icon': 'fa-check-circle',
                'points_required': 10,
                'badge_type': 'achievement'
            },
            {
                'name': 'Course Completer',
                'description': 'Completed an entire course',
                'icon': 'fa-graduation-cap',
                'points_required': 30,
                'badge_type': 'achievement'
            },
            {
                'name': 'Quiz Master',
                'description': 'Scored above 80% on a quiz',
                'icon': 'fa-star',
                'points_required': 15,
                'badge_type': 'achievement'
            },
            {
                'name': 'Consistent Learner',
                'description': 'Logged in for 3 consecutive days',
                'icon': 'fa-calendar-check',
                'points_required': 20,
                'badge_type': 'achievement'
            }
        ]
        
        for badge_info in badges:
            badge, created = Badge.objects.get_or_create(
                name=badge_info['name'],
                defaults={
                    'description': badge_info['description'],
                    'icon': badge_info['icon'],
                    'points_required': badge_info['points_required'],
                    'badge_type': badge_info['badge_type']
                }
            )
            
            if created:
                self.stdout.write(f'Created badge: {badge.name}')
            else:
                self.stdout.write(f'Badge already exists: {badge.name}')
    
    def award_quiz_badges(self):
        """Award badges for quiz attempts"""
        # Check for first quiz completion badge
        first_quiz_badge = Badge.objects.filter(name='First Quiz Completed').first()
        if not first_quiz_badge:
            self.stdout.write('First Quiz Completed badge not found')
            return
            
        # Check for quiz master badge
        quiz_master_badge = Badge.objects.filter(name='Quiz Master').first()
        if not quiz_master_badge:
            self.stdout.write('Quiz Master badge not found')
            return
            
        # Get all users with quiz attempts
        users_with_quizzes = User.objects.filter(quiz_attempts__completed=True).distinct()
        self.stdout.write(f'Found {users_with_quizzes.count()} users with quiz attempts')
        
        for user in users_with_quizzes:
            # Get completed quiz attempts
            quiz_attempts = QuizAttempt.objects.filter(user=user, completed=True)
            
            if quiz_attempts.exists():
                # Award first quiz badge
                if not UserBadge.objects.filter(user=user, badge=first_quiz_badge).exists():
                    UserBadge.objects.create(
                        user=user,
                        badge=first_quiz_badge
                    )
                    
                    # Award points
                    PointsTransaction.objects.create(
                        user=user,
                        points=first_quiz_badge.points_required,
                        transaction_type='bonus',
                        description=f"Earned {first_quiz_badge.name} badge"
                    )
                    
                    self.stdout.write(f'Awarded First Quiz Completed badge to {user.username}')
            
            # Check for high-scoring quizzes (above 80%)
            high_scoring_attempts = []
            for attempt in quiz_attempts:
                # Use score_percentage property if available, otherwise calculate
                if hasattr(attempt, 'score_percentage'):
                    score_pct = attempt.score_percentage
                else:
                    score_pct = (attempt.score / attempt.max_score * 100) if attempt.max_score > 0 else 0
                
                if score_pct >= 80:
                    high_scoring_attempts.append(attempt)
            
            if high_scoring_attempts and not UserBadge.objects.filter(user=user, badge=quiz_master_badge).exists():
                UserBadge.objects.create(
                    user=user,
                    badge=quiz_master_badge
                )
                
                # Award points
                PointsTransaction.objects.create(
                    user=user,
                    points=quiz_master_badge.points_required,
                    transaction_type='bonus',
                    description=f"Earned {quiz_master_badge.name} badge"
                )
                
                self.stdout.write(f'Awarded Quiz Master badge to {user.username}') 