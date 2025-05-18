import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum
from gamification.models import Leaderboard, PointsTransaction

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates and updates leaderboard data'

    def handle(self, *args, **options):
        self.stdout.write('Creating leaderboard data...')
        
        # Get all students
        students = User.objects.filter(is_staff=False, is_superuser=False)
        
        # Generate or update leaderboard entries
        for i, student in enumerate(students):
            # Calculate total points from transactions
            total_points = PointsTransaction.objects.filter(
                user=student,
                transaction_type__in=['earned', 'bonus']
            ).aggregate(total=Sum('points'))['total'] or 0
            
            # Add additional random points to make the leaderboard more interesting
            total_points += random.randint(50, 500)
            
            # Create or update leaderboard entry
            leaderboard, created = Leaderboard.objects.update_or_create(
                user=student,
                defaults={
                    'points': total_points,
                    'last_updated': timezone.now()
                }
            )
            
            if created:
                self.stdout.write(f'Created leaderboard entry for {student.username} with {total_points} points')
            else:
                self.stdout.write(f'Updated leaderboard entry for {student.username} to {total_points} points')
        
        # Update ranks
        self.update_ranks()
        
        self.stdout.write(self.style.SUCCESS('Leaderboard data created successfully!'))
    
    def update_ranks(self):
        """Update ranks for all leaderboard entries"""
        leaderboards = Leaderboard.objects.all().order_by('-points')
        
        for i, leaderboard in enumerate(leaderboards, 1):
            if leaderboard.rank != i:
                leaderboard.rank = i
                leaderboard.save(update_fields=['rank'])
                self.stdout.write(f'Updated rank for {leaderboard.user.username} to {i}') 