# leaderboard/views.py
from rest_framework import generics, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import Leaderboard, GlobalLeaderboard, Achievement
from .serializers import (
    LeaderboardSerializer, LeaderboardCreateSerializer,
    GlobalLeaderboardSerializer, AchievementSerializer,
    UserStatsSerializer, ExamLeaderboardSerializer
)
from exams.models import ExamSession

User = get_user_model()

class LeaderboardViewSet(viewsets.ModelViewSet):
    queryset = Leaderboard.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LeaderboardCreateSerializer
        return LeaderboardSerializer
    
    def get_queryset(self):
        queryset = Leaderboard.objects.select_related('user', 'exam_session')
        
        # Filter by exam session
        exam_session_id = self.request.query_params.get('exam_session')
        if exam_session_id:
            queryset = queryset.filter(exam_session_id=exam_session_id)
        
        # Filter by user
        user_id = self.request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.order_by('rank')
    
    @action(detail=False, methods=['get'])
    def top_performers(self, request):
        """Get top performers across all exams or specific exam"""
        exam_session_id = request.query_params.get('exam_session')
        limit = int(request.query_params.get('limit', 10))
        
        if exam_session_id:
            queryset = self.get_queryset().filter(exam_session_id=exam_session_id)[:limit]
        else:
            # Get top performers globally (best rank per user)
            queryset = Leaderboard.objects.filter(
                rank=1
            ).select_related('user', 'exam_session')[:limit]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_rankings(self, request):
        """Get current user's rankings"""
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class GlobalLeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GlobalLeaderboard.objects.select_related('user')
    serializer_class = GlobalLeaderboardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.order_by('global_rank')
    
    @action(detail=False, methods=['get'])
    def top_global(self, request):
        """Get top global performers"""
        limit = int(request.query_params.get('limit', 50))
        queryset = self.get_queryset()[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_global_rank(self, request):
        """Get current user's global ranking"""
        try:
            global_rank = GlobalLeaderboard.objects.get(user=request.user)
            serializer = self.get_serializer(global_rank)
            return Response(serializer.data)
        except GlobalLeaderboard.DoesNotExist:
            return Response(
                {'detail': 'Global ranking not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class ExamLeaderboardView(generics.RetrieveAPIView):
    """Get detailed leaderboard for a specific exam"""
    queryset = ExamSession.objects.all()
    serializer_class = ExamLeaderboardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        exam_session_id = self.kwargs.get('exam_session_id')
        return get_object_or_404(ExamSession, id=exam_session_id)

class UserStatsView(generics.RetrieveAPIView):
    """Get comprehensive user statistics"""
    serializer_class = UserStatsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        if user_id:
            return get_object_or_404(User, id=user_id)
        return self.request.user

class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Achievement.objects.select_related('user', 'exam_session')
    serializer_class = AchievementSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = self.queryset
        
        # Filter by user
        user_id = self.request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by achievement type
        achievement_type = self.request.query_params.get('type')
        if achievement_type:
            queryset = queryset.filter(achievement_type=achievement_type)
        
        return queryset.order_by('-earned_at')
    
    @action(detail=False, methods=['get'])
    def my_achievements(self, request):
        """Get current user's achievements"""
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent_achievements(self, request):
        """Get recent achievements across all users"""
        limit = int(request.query_params.get('limit', 20))
        queryset = self.get_queryset()[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class LeaderboardStatsView(generics.GenericAPIView):
    """Get general leaderboard statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from django.db.models import Count, Avg, Max, Min
        
        # General statistics
        total_users = User.objects.count()
        total_exams = ExamSession.objects.count()
        total_attempts = Leaderboard.objects.count()
        
        # Score statistics
        score_stats = Leaderboard.objects.aggregate(
            avg_score=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score')
        )
        
        # Top performers
        top_performers = GlobalLeaderboard.objects.filter(
            global_rank__lte=10
        ).select_related('user')
        
        # Recent activity
        recent_attempts = Leaderboard.objects.select_related(
            'user', 'exam_session'
        ).order_by('-created_at')[:5]
        
        return Response({
            'general_stats': {
                'total_users': total_users,
                'total_exams': total_exams,
                'total_attempts': total_attempts,
                'average_score': round(score_stats['avg_score'] or 0, 2),
                'highest_score': score_stats['max_score'] or 0,
                'lowest_score': score_stats['min_score'] or 0,
            },
            'top_performers': GlobalLeaderboardSerializer(top_performers, many=True).data,
            'recent_activity': LeaderboardSerializer(recent_attempts, many=True).data
        })