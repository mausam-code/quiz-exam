from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib import admin
from accounts.views import LoginView, RegisterView, ProfileView, UserStatsView, CreateTeacherView, logout_view

urlpatterns = [
    # Login page - serves the HTML login form
    path("", TemplateView.as_view(template_name="login.html"), name="login"),
    
    # Alternative login URL
    path("login/", TemplateView.as_view(template_name="login.html"), name="login_alt"),
    
    # API endpoints for authentication
    path("api/auth/login/", LoginView.as_view(), name="api_login"),
    path("api/auth/register/", RegisterView.as_view(), name="api_register"),
    path("api/auth/profile/", ProfileView.as_view(), name="api_profile"),
    path("api/auth/stats/", UserStatsView.as_view(), name="api_stats"),
    path("api/auth/create-teacher/", CreateTeacherView.as_view(), name="api_create_teacher"),
    path("api/auth/logout/", logout_view, name="api_logout"),
    
    # Staff/Home page (you'll need to create this view)
    path("staff/", TemplateView.as_view(template_name="staff_dashboard.html"), name="staff_dashboard"),
    
    # Django admin
    path('admin/', admin.site.urls),
]