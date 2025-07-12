from django.urls import path
from .views import(
    RegisterView, LoginView, ProfileView, UserStatsView,
    CreateTeacherView, logout_view)

urlpatterns = [
    path('register/', RegisterView.as_view(), name ='register'),
    path('login/',LoginView.as_view(), name ='login'),
    path('logout/',logout_view,name='logout'),
    path('profile/',ProfileView.as_view(), name ='profile'),
    path('stats/',UserStatsView.as_view(), name = 'user-stats'),
    path('create-teacher/',CreateTeacherView.as_view(), name = 'create-teacher'),
]