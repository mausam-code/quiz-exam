from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import ExamSession, Question, ExamAttempt, ExamPayment
from .serializers import (
    ExamSessionSerializer, ExamSessionCreateSerializer,
    QuestionSerializer, QuestionCreateSerializer,
    ExamAttemptSerializer, AnswerSubmissionSerializer,
    ExamPaymentSerializer
)
from .filters import ExamSessionFilter
from . models import IsTeacherOrAdmin, IsOwnerOrReadOnly

class ExamSessionListView(generics.ListAPIView):
    queryset = ExamSession.objects.filter(status__in=['scheduled', 'active'])
    serializer_class = ExamSessionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ExamSessionFilter
    search_fields = ['title', 'description', 'created_by__username']
    ordering_fields = ['start_time', 'created_at', 'price', 'difficulty']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filter based on user type
        if user.is_normal_user:
            # Normal users see only public exams or exams they're allowed to take
            queryset = queryset.filter(
                Q(is_public=True) | Q(allowed_users=user)
            ).distinct()
        
        return queryset

class ExamSessionCreateView(generics.CreateAPIView):
    serializer_class = ExamSessionCreateSerializer
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ExamSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ExamSession.objects.all()
    serializer_class = ExamSessionSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ExamSessionCreateSerializer
        return ExamSessionSerializer

class MyExamsView(generics.ListAPIView):
    serializer_class = ExamSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_teacher or user.is_admin_user:
            return ExamSession.objects.filter(created_by=user)
        else:
            # Return exams the user has attempted
            return ExamSession.objects.filter(
                exam_attempts__user=user
            ).distinct()

class ExamQuestionsView(generics.ListCreateAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        exam_id = self.kwargs['exam_id']
        exam = get_object_or_404(ExamSession, id=exam_id)
        
        # Check if user can access questions
        user = self.request.user
        if user == exam.created_by or user.is_admin_user:
            # Creator and admin can see all questions with answers
            return exam.questions.all()
        elif exam.exam_attempts.filter(user=user).exists():
            # User who attempted can see questions
            return exam.questions.all()
        else:
            # Check if user can participate
            can_participate, message = exam.can_user_participate(user)
            if not can_participate:
                return Question.objects.none()
            return exam.questions.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionCreateSerializer
        return QuestionSerializer
    
    def perform_create(self, serializer):
        exam_id = self.kwargs['exam_id']
        exam = get_object_or_404(ExamSession, id=exam_id)
        
        # Check permissions
        if self.request.user != exam.created_by and not self.request.user.is_admin_user:
            raise permissions.PermissionDenied("Only exam creator can add questions")
        
        serializer.save(exam_session=exam)

class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return QuestionCreateSerializer
        return QuestionSerializer
    
    def get_object(self):
        question = super().get_object()
        user = self.request.user
        
        # Check if user can access this question
        if (user != question.exam_session.created_by and 
            not user.is_admin_user and
            not question.exam_session.exam_attempts.filter(user=user).exists()):
            raise permissions.PermissionDenied("You don't have permission to access this question")
        
        return question

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_exam(request, exam_id):
    """Start an exam attempt"""
    exam = get_object_or_404(ExamSession, id=exam_id)
    user = request.user
    
    # Check if user can participate
    can_participate, message = exam.can_user_participate(user)
    if not can_participate:
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if exam is paid and payment is required
    if exam.is_paid:
        payment = ExamPayment.objects.filter(
            user=user,
            exam_session=exam,
            status='completed'
        ).first()
        
        if not payment:
            return Response({
                'error': 'Payment required for this exam',
                'payment_required': True,
                'amount': exam.price
            }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    # Create exam attempt
    attempt, created = ExamAttempt.objects.get_or_create(
        user=user,
        exam_session=exam,
        defaults={'payment_status': 'completed' if not exam.is_paid else 'pending'}
    )
    
    if not created:
        return Response({'error': 'You have already started this exam'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'message': 'Exam started successfully',
        'attempt_id': attempt.id,
        'start_time': attempt.start_time,
        'duration': exam.duration
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_answers(request, exam_id):
    """Submit answers for an exam"""
    exam = get_object_or_404(ExamSession, id=exam_id)
    user = request.user
    
    # Get the exam attempt
    try:
        attempt = ExamAttempt.objects.get(user=user, exam_session=exam)
    except ExamAttempt.DoesNotExist:
        return Response({'error': 'No exam attempt found'}, status=status.HTTP_404_NOT_FOUND)
    
    if attempt.is_submitted:
        return Response({'error': 'Exam already submitted'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate answers
    serializer = AnswerSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Save answers and submit exam
    attempt.answers = serializer.validated_data['answers']
    attempt.submit_exam()
    
    return Response({
        'message': 'Exam submitted successfully',
        'score': attempt.score,
        'percentage': attempt.percentage,
        'total_marks': attempt.total_marks
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exam_result(request, exam_id):
    """Get exam result"""
    exam = get_object_or_404(ExamSession, id=exam_id)
    user = request.user
    
    try:
        attempt = ExamAttempt.objects.get(user=user, exam_session=exam)
    except ExamAttempt.DoesNotExist:
        return Response({'error': 'No exam attempt found'}, status=status.HTTP_404_NOT_FOUND)
    
    if not attempt.is_submitted:
        return Response({'error': 'Exam not yet submitted'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get detailed results
    questions = exam.questions.all()
    detailed_results = []
    
    for question in questions:
        user_answer = attempt.answers.get(str(question.id))
        is_correct = attempt.is_answer_correct(question, user_answer) if user_answer else False
        
        detailed_results.append({
            'question_id': question.id,
            'question_text': question.question_text,
            'user_answer': user_answer,
            'correct_answer': question.correct_answer,
            'is_correct': is_correct,
            'marks': question.marks,
            'explanation': question.explanation
        })
    
    return Response({
        'attempt': ExamAttemptSerializer(attempt).data,
        'detailed_results': detailed_results
    })

class ExamAttemptListView(generics.ListAPIView):
    serializer_class = ExamAttemptSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_teacher or user.is_admin_user:
            # Teachers and admins can see attempts for their exams
            return ExamAttempt.objects.filter(
                exam_session__created_by=user
            )
        else:
            # Normal users can only see their own attempts
            return ExamAttempt.objects.filter(user=user)

class ExamAttemptDetailView(generics.RetrieveAPIView):
    serializer_class = ExamAttemptSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        attempt = get_object_or_404(ExamAttempt, id=self.kwargs['pk'])
        user = self.request.user
        
        # Check permissions
        if (user != attempt.user and 
            user != attempt.exam_session.created_by and 
            not user.is_admin_user):
            raise permissions.PermissionDenied("You don't have permission to view this attempt")
        
        return attempt

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_payment(request, exam_id):
    """Process payment for paid exam"""
    exam = get_object_or_404(ExamSession, id=exam_id)
    user = request.user
    
    if not exam.is_paid:
        return Response({'error': 'This exam is free'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if already paid
    if ExamPayment.objects.filter(user=user, exam_session=exam, status='completed').exists():
        return Response({'error': 'Already paid for this exam'}, status=status.HTTP_400_BAD_REQUEST)
    
    # In a real implementation, you would integrate with Stripe or another payment gateway
    # For now, we'll simulate a successful payment
    payment = ExamPayment.objects.create(
        user=user,
        exam_session=exam,
        amount=exam.price,
        payment_id=f"pay_{exam.id}_{user.id}_{timezone.now().timestamp()}",
        payment_method="card",
        status="completed"
    )
    
    return Response({
        'message': 'Payment processed successfully',
        'payment_id': payment.payment_id,
        'amount': payment.amount
    })