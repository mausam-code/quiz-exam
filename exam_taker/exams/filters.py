import django_filters
from .models import ExamSession

class ExamSessionFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    is_free = django_filters.BooleanFilter(field_name='is_paid', lookup_expr='exact', exclude=True)
    difficulty = django_filters.ChoiceFilter(choices=ExamSession.DIFFICULTY_CHOICES)
    status = django_filters.ChoiceFilter(choices=ExamSession.STATUS_CHOICES)
    
    class Meta:
        model = ExamSession
        fields = ['is_paid', 'difficulty', 'status', 'is_public']

# exams/permissions.py
from rest_framework import permissions

class IsTeacherOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow teachers and admins to create exams.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_teacher or request.user.is_admin_user
        )

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the exam.
        return obj.created_by == request.user or request.user.is_admin_user

