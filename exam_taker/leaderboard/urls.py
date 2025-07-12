# leaderboard/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewsets
router = DefaultRouter()
router.register(r'leaderboards', views.LeaderboardViewSet, basename='leaderboard')
router.register(r'global', views.GlobalLeaderboardViewSet, basename='global-leaderboard')
router.register(r'achievements', views.AchievementViewSet, basename='achievement')

app_name = 'leaderboard'

urlpatterns = [
    # ViewSet URLs
    path('api/', include(router.urls)),
    
    # Individual view URLs
    path('api/exam/<int:exam_session_id>/leaderboard/', 
         views.ExamLeaderboardView.as_view(), 
         name='exam-leaderboard'),
    
    path('api/user/<int:user_id>/stats/', 
         views.UserStatsView.as_view(), 
         name='user-stats'),
    
    path('api/my-stats/', 
         views.UserStatsView.as_view(), 
         name='my-stats'),
    
    path('api/stats/', 
         views.LeaderboardStatsView.as_view(), 
         name='leaderboard-stats'),
]

# Alternative URL patterns for more RESTful structure
urlpatterns += [
    # Leaderboard specific URLs
    path('api/leaderboards/top/', 
         views.LeaderboardViewSet.as_view({'get': 'top_performers'}), 
         name='top-performers'),
    
    path('api/leaderboards/mine/', 
         views.LeaderboardViewSet.as_view({'get': 'my_rankings'}), 
         name='my-rankings'),
    
    # Global leaderboard URLs
    path('api/global/top/', 
         views.GlobalLeaderboardViewSet.as_view({'get': 'top_global'}), 
         name='top-global'),
    
    path('api/global/mine/', 
         views.GlobalLeaderboardViewSet.as_view({'get': 'my_global_rank'}), 
         name='my-global-rank'),
    
    # Achievement URLs
    path('api/achievements/mine/', 
         views.AchievementViewSet.as_view({'get': 'my_achievements'}), 
         name='my-achievements'),
    
    path('api/achievements/recent/', 
         views.AchievementViewSet.as_view({'get': 'recent_achievements'}), 
         name='recent-achievements'),
]