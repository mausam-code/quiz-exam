# leaderboard/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Leaderboard, GlobalLeaderboard, Achievement
from exams.models import ExamSession

User = get_user_model()

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for leaderboard display"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class ExamSessionBasicSerializer(serializers.ModelSerializer):
    """Basic exam session info for leaderboard display"""
    class Meta:
        model = ExamSession
        fields = ['id', 'title', 'description', 'total_questions']

class LeaderboardSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    exam_session = ExamSessionBasicSerializer(read_only=True)
    time_taken_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Leaderboard
        fields = [
            'id', 'user', 'exam_session', 'score', 'percentage', 
            'time_taken', 'time_taken_formatted', 'rank', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['rank', 'created_at', 'updated_at']
    
    def get_time_taken_formatted(self, obj):
        """Convert seconds to MM:SS format"""
        minutes = obj.time_taken // 60
        seconds = obj.time_taken % 60
        return f"{minutes:02d}:{seconds:02d}"

class LeaderboardCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating leaderboard entries"""
    class Meta:
        model = Leaderboard
        fields = ['exam_session', 'user', 'score', 'percentage', 'time_taken']
    
    def create(self, validated_data):
        # Calculate rank based on score and time
        exam_session = validated_data['exam_session']
        score = validated_data['score']
        time_taken = validated_data['time_taken']
        
        # Count users with better scores or same score but faster time
        better_entries = Leaderboard.objects.filter(
            exam_session=exam_session
        ).filter(
            models.Q(score__gt=score) | 
            (models.Q(score=score) & models.Q(time_taken__lt=time_taken))
        ).count()
        
        validated_data['rank'] = better_entries + 1
        
        # Update ranks of users with worse performance
        Leaderboard.objects.filter(
            exam_session=exam_session,
            rank__gte=validated_data['rank']
        ).update(rank=models.F('rank') + 1)
        
        return super().create(validated_data)

class GlobalLeaderboardSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    total_time_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = GlobalLeaderboard
        fields = [
            'id', 'user', 'total_exams', 'total_score', 
            'average_score', 'global_rank', 'best_score',
            'total_time_spent', 'total_time_formatted',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['global_rank', 'created_at', 'updated_at']
    
    def get_total_time_formatted(self, obj):
        """Convert total seconds to hours:minutes format"""
        hours = obj.total_time_spent // 3600
        minutes = (obj.total_time_spent % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"

class AchievementSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    exam_session = ExamSessionBasicSerializer(read_only=True)
    achievement_display = serializers.CharField(source='get_achievement_type_display', read_only=True)
    
    class Meta:
        model = Achievement
        fields = [
            'id', 'user', 'achievement_type', 'achievement_display',
            'exam_session', 'earned_at', 'description'
        ]
        read_only_fields = ['earned_at']

class UserStatsSerializer(serializers.Serializer):
    """Comprehensive user statistics"""
    user = UserBasicSerializer(read_only=True)
    global_stats = GlobalLeaderboardSerializer(source='global_leaderboard', read_only=True)
    recent_performances = serializers.SerializerMethodField()
    achievements = serializers.SerializerMethodField()
    rank_distribution = serializers.SerializerMethodField()
    
    def get_recent_performances(self, obj):
        """Get user's recent exam performances"""
        recent = obj.leaderboard_entries.order_by('-created_at')[:5]
        return LeaderboardSerializer(recent, many=True).data
    
    def get_achievements(self, obj):
        """Get user's achievements"""
        achievements = obj.achievements.order_by('-earned_at')[:10]
        return AchievementSerializer(achievements, many=True).data
    
    def get_rank_distribution(self, obj):
        """Get distribution of user's ranks"""
        from django.db.models import Count, Case, When, IntegerField
        
        distribution = obj.leaderboard_entries.aggregate(
            first_place=Count(Case(When(rank=1, then=1), output_field=IntegerField())),
            top_3=Count(Case(When(rank__lte=3, then=1), output_field=IntegerField())),
            top_10=Count(Case(When(rank__lte=10, then=1), output_field=IntegerField())),
            total_exams=Count('id')
        )
        
        return {
            'first_place': distribution['first_place'],
            'top_3': distribution['top_3'],
            'top_10': distribution['top_10'],
            'total_exams': distribution['total_exams']
        }

class ExamLeaderboardSerializer(serializers.ModelSerializer):
    """Detailed leaderboard for a specific exam"""
    leaderboard_entries = LeaderboardSerializer(many=True, read_only=True)
    total_participants = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()
    top_score = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamSession
        fields = [
            'id', 'title', 'description', 'total_questions',
            'leaderboard_entries', 'total_participants', 
            'average_score', 'top_score'
        ]
    
    def get_total_participants(self, obj):
        return obj.leaderboard_entries.count()
    
    def get_average_score(self, obj):
        from django.db.models import Avg
        avg = obj.leaderboard_entries.aggregate(avg_score=Avg('score'))
        return round(avg['avg_score'] or 0, 2)
    
    def get_top_score(self, obj):
        from django.db.models import Max
        top = obj.leaderboard_entries.aggregate(max_score=Max('score'))
        return top['max_score'] or 0