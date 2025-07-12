# leaderboard/utils.py
from django.db.models import F, Q, Count, Avg, Max
from django.contrib.auth import get_user_model
from .models import Leaderboard, GlobalLeaderboard, Achievement
from exams.models import ExamSession, ExamAttempt

User = get_user_model()

def update_leaderboard_from_attempt(exam_attempt):
    """
    Create or update leaderboard entry from an exam attempt
    """
    # Calculate score and percentage
    total_questions = exam_attempt.exam_session.total_questions
    correct_answers = exam_attempt.score
    percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    # Create or update leaderboard entry
    leaderboard_entry, created = Leaderboard.objects.get_or_create(
        exam_session=exam_attempt.exam_session,
        user=exam_attempt.user,
        defaults={
            'score': correct_answers,
            'percentage': percentage,
            'time_taken': exam_attempt.time_taken,
            'rank': 1  # Will be recalculated
        }
    )
    
    # If not created, update with better performance
    if not created:
        # Only update if this is a better performance
        if (correct_answers > leaderboard_entry.score or 
            (correct_answers == leaderboard_entry.score and 
             exam_attempt.time_taken < leaderboard_entry.time_taken)):
            
            leaderboard_entry.score = correct_answers
            leaderboard_entry.percentage = percentage
            leaderboard_entry.time_taken = exam_attempt.time_taken
            leaderboard_entry.save()
    
    # Recalculate ranks for this exam session
    recalculate_ranks(exam_attempt.exam_session)
    
    # Update global leaderboard
    update_global_leaderboard(exam_attempt.user)
    
    # Check and award achievements
    check_achievements(leaderboard_entry)
    
    return leaderboard_entry

def recalculate_ranks(exam_session):
    """
    Recalculate ranks for all users in an exam session
    """
    # Get all leaderboard entries for this exam session, ordered by performance
    entries = Leaderboard.objects.filter(
        exam_session=exam_session
    ).order_by('-score', 'time_taken')
    
    # Update ranks
    for index, entry in enumerate(entries):
        entry.rank = index + 1
        entry.save(update_fields=['rank'])

def update_global_leaderboard(user):
    """
    Update or create global leaderboard entry for a user
    """
    global_entry, created = GlobalLeaderboard.objects.get_or_create(
        user=user,
        defaults={
            'total_exams': 0,
            'total_score': 0.0,
            'average_score': 0.0,
            'best_score': 0.0,
            'total_time_spent': 0,
        }
    )
    
    # Update statistics
    global_entry.update_stats()
    
    # Recalculate global ranks
    recalculate_global_ranks()

def recalculate_global_ranks():
    """
    Recalculate global ranks for all users
    """
    # Order by average score (descending), then by total exams (descending)
    global_entries = GlobalLeaderboard.objects.filter(
        total_exams__gt=0
    ).order_by('-average_score', '-total_exams', 'total_time_spent')
    
    for index, entry in enumerate(global_entries):
        entry.global_rank = index + 1
        entry.save(update_fields=['global_rank'])

def check_achievements(leaderboard_entry):
    """
    Check and award achievements based on leaderboard performance
    """
    user = leaderboard_entry.user
    exam_session = leaderboard_entry.exam_session
    
    # First Place Achievement
    if leaderboard_entry.rank == 1:
        Achievement.objects.get_or_create(
            user=user,
            achievement_type='first_place',
            exam_session=exam_session,
            defaults={
                'description': f'Achieved 1st place in {exam_session.title}'
            }
        )
    
    # Top 3 Achievement
    if leaderboard_entry.rank <= 3:
        Achievement.objects.get_or_create(
            user=user,
            achievement_type='top_3',
            exam_session=exam_session,
            defaults={
                'description': f'Achieved top 3 in {exam_session.title}'
            }
        )
    
    # Top 10 Achievement
    if leaderboard_entry.rank <= 10:
        Achievement.objects.get_or_create(
            user=user,
            achievement_type='top_10',
            exam_session=exam_session,
            defaults={
                'description': f'Achieved top 10 in {exam_session.title}'
            }
        )
    
    # Perfect Score Achievement
    if leaderboard_entry.percentage == 100:
        Achievement.objects.get_or_create(
            user=user,
            achievement_type='perfect_score',
            exam_session=exam_session,
            defaults={
                'description': f'Achieved perfect score in {exam_session.title}'
            }
        )
    
    # Speed Demon Achievement (fastest time among top 10% scorers)
    total_participants = Leaderboard.objects.filter(
        exam_session=exam_session
    ).count()
    
    if total_participants >= 10:  # Only if there are enough participants
        top_10_percent = max(1, total_participants // 10)
        top_scorers = Leaderboard.objects.filter(
            exam_session=exam_session
        ).order_by('-score')[:top_10_percent]
        
        fastest_among_top = top_scorers.order_by('time_taken').first()
        if fastest_among_top == leaderboard_entry:
            Achievement.objects.get_or_create(
                user=user,
                achievement_type='speed_demon',
                exam_session=exam_session,
                defaults={
                    'description': f'Fastest completion time among top performers in {exam_session.title}'
                }
            )
    
    # Consistent Performer Achievement (top 3 in 5 different exams)
    top_3_count = Leaderboard.objects.filter(
        user=user,
        rank__lte=3
    ).count()
    
    if top_3_count >= 5:
        Achievement.objects.get_or_create(
            user=user,
            achievement_type='consistent',
            defaults={
                'description': 'Achieved top 3 in 5 different exams'
            }
        )

def get_user_performance_summary(user):
    """
    Get comprehensive performance summary for a user
    """
    # Basic stats
    total_exams = Leaderboard.objects.filter(user=user).count()
    
    if total_exams == 0:
        return {
            'total_exams': 0,
            'average_score': 0,
            'best_rank': None,
            'achievements_count': 0,
            'performance_trend': []
        }
    
    # Performance metrics
    user_entries = Leaderboard.objects.filter(user=user)
    
    stats = user_entries.aggregate(
        avg_score=Avg('score'),
        best_score=Max('score'),
        best_rank=models.Min('rank'),
        total_time=models.Sum('time_taken')
    )
    
    # Achievement count
    achievements_count = Achievement.objects.filter(user=user).count()
    
    # Performance trend (last 10 exams)
    recent_performances = user_entries.order_by('-created_at')[:10]
    trend_data = [
        {
            'exam': entry.exam_session.title,
            'score': entry.score,
            'rank': entry.rank,
            'date': entry.created_at.date()
        }
        for entry in recent_performances
    ]
    
    return {
        'total_exams': total_exams,
        'average_score': round(stats['avg_score'] or 0, 2),
        'best_score': stats['best_score'] or 0,
        'best_rank': stats['best_rank'],
        'total_time_spent': stats['total_time'] or 0,
        'achievements_count': achievements_count,
        'performance_trend': trend_data
    }

def get_exam_statistics(exam_session):
    """
    Get comprehensive statistics for an exam session
    """
    entries = Leaderboard.objects.filter(exam_session=exam_session)
    
    if not entries.exists():
        return {
            'total_participants': 0,
            'average_score': 0,
            'median_score': 0,
            'highest_score': 0,
            'lowest_score': 0,
            'average_time': 0,
            'completion_rate': 0
        }
    
    stats = entries.aggregate(
        total_participants=Count('id'),
        avg_score=Avg('score'),
        max_score=Max('score'),
        min_score=models.Min('score'),
        avg_time=Avg('time_taken')
    )
    
    # Calculate median score
    scores = list(entries.values_list('score', flat=True).order_by('score'))
    n = len(scores)
    median_score = scores[n // 2] if n % 2 == 1 else (scores[n // 2 - 1] + scores[n // 2]) / 2
    
    return {
        'total_participants': stats['total_participants'],
        'average_score': round(stats['avg_score'] or 0, 2),
        'median_score': round(median_score, 2),
        'highest_score': stats['max_score'] or 0,
        'lowest_score': stats['min_score'] or 0,
        'average_time': round(stats['avg_time'] or 0, 2),
        'completion_rate': 100  # Assuming all entries are completed attempts
    }