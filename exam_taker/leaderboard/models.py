# leaderboard/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Avg, Sum, Count
from exams.models import ExamSession, ExamAttempt

User = get_user_model()

class Leaderboard(models.Model):
    exam_session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name='leaderboard_entries'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leaderboard_entries'
    )
    score = models.FloatField()
    percentage = models.FloatField()
    time_taken = models.IntegerField(help_text="Time taken in seconds")
    rank = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['exam_session', 'user']
        ordering = ['rank']
        indexes = [
            models.Index(fields=['exam_session', 'rank']),
            models.Index(fields=['exam_session', 'score']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Rank {self.rank} - {self.exam_session.title}"

class GlobalLeaderboard(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='global_leaderboard'
    )
    total_exams = models.IntegerField(default=0)
    total_score = models.FloatField(default=0.0)
    average_score = models.FloatField(default=0.0)
    global_rank = models.IntegerField(null=True, blank=True)
    best_score = models.FloatField(default=0.0)
    total_time_spent = models.IntegerField(default=0, help_text="Total time in seconds")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['global_rank']
        indexes = [
            models.Index(fields=['global_rank']),
            models.Index(fields=['average_score']),
            models.Index(fields=['total_score']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Global Rank {self.global_rank}"
    
    def update_stats(self):
        """Update user statistics from their leaderboard entries"""
        stats = self.user.leaderboard_entries.aggregate(
            total_exams=Count('id'),
            total_score=Sum('score'),
            average_score=Avg('score'),
            best_score=models.Max('score'),
            total_time=Sum('time_taken')
        )
        
        self.total_exams = stats['total_exams'] or 0
        self.total_score = stats['total_score'] or 0.0
        self.average_score = stats['average_score'] or 0.0
        self.best_score = stats['best_score'] or 0.0
        self.total_time_spent = stats['total_time'] or 0
        self.save()

class LeaderboardManager(models.Manager):
    def get_top_performers(self, exam_session, limit=10):
        """Get top performers for a specific exam session"""
        return self.filter(exam_session=exam_session).order_by('rank')[:limit]
    
    def get_user_rank(self, exam_session, user):
        """Get user's rank in a specific exam session"""
        try:
            return self.get(exam_session=exam_session, user=user).rank
        except self.model.DoesNotExist:
            return None

# Add custom manager to Leaderboard model
Leaderboard.add_to_class('objects', LeaderboardManager())

class Achievement(models.Model):
    ACHIEVEMENT_TYPES = [
        ('first_place', 'First Place'),
        ('top_3', 'Top 3'),
        ('top_10', 'Top 10'),
        ('perfect_score', 'Perfect Score'),
        ('speed_demon', 'Speed Demon'),
        ('consistent', 'Consistent Performer'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='achievements'
    )
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    exam_session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name='achievements',
        null=True,
        blank=True
    )
    earned_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['user', 'achievement_type', 'exam_session']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_achievement_type_display()}"