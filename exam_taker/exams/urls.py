# exams/urls.py
from django.urls import path
from .views import (
    ExamSessionListView, ExamSessionCreateView, ExamSessionDetailView,
    MyExamsView, ExamQuestionsView, QuestionDetailView,
    start_exam, submit_answers, exam_result,
    ExamAttemptListView, ExamAttemptDetailView, process_payment
)

urlpatterns = [
    # Exam sessions
    path('', ExamSessionListView.as_view(), name='exam-list'),
    path('create/', ExamSessionCreateView.as_view(), name='exam-create'),
    path('<int:pk>/', ExamSessionDetailView.as_view(), name='exam-detail'),
    path('my-exams/', MyExamsView.as_view(), name='my-exams'),
    
    # Questions
    path('<int:exam_id>/questions/', ExamQuestionsView.as_view(), name='exam-questions'),
    path('questions/<int:pk>/', QuestionDetailView.as_view(), name='question-detail'),
    
    # Exam taking
    path('<int:exam_id>/start/', start_exam, name='start-exam'),
    path('<int:exam_id>/submit/', submit_answers, name='submit-answers'),
    path('<int:exam_id>/result/', exam_result, name='exam-result'),
    
    # Exam attempts
    path('attempts/', ExamAttemptListView.as_view(), name='exam-attempts'),
    path('attempts/<int:pk>/', ExamAttemptDetailView.as_view(), name='exam-attempt-detail'),
    
    # Payment
    path('<int:exam_id>/payment/', process_payment, name='process-payment'),
]