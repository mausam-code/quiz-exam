from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()

class ExamSession(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    duration = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        help_text="Duration in minutes"
    )
    
    # Pricing
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    
    # Scheduling
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # Configuration
    max_participants = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1)]
    )
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    
    # Permissions
    is_public = models.BooleanField(default=True)
    allowed_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='allowed_exams'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_exams'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Statistics
    total_participants = models.IntegerField(default=0)
    average_score = models.FloatField(default=0.0)
    highest_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_time']),
            models.Index(fields=['is_paid', 'is_public']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    @property
    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.status == 'active'
    
    @property
    def is_upcoming(self):
        return timezone.now() < self.start_time
    
    @property
    def is_finished(self):
        return timezone.now() > self.end_time
    
    @property
    def participants_count(self):
        return self.exam_attempts.filter(is_completed=True).count()
    
    def can_user_participate(self, user):
        """Check if user can participate in this exam"""
        if not self.is_public and user not in self.allowed_users.all():
            return False, "You are not allowed to take this exam"
        
        if self.participants_count >= self.max_participants:
            return False, "Maximum participants limit reached"
        
        if not self.is_active:
            return False, "Exam is not currently active"
        
        # Check if user already attempted
        if self.exam_attempts.filter(user=user).exists():
            return False, "You have already attempted this exam"
        
        return True, "You can participate"
    
    def update_statistics(self):
        """Update exam statistics"""
        completed_attempts = self.exam_attempts.filter(is_completed=True)
        
        if completed_attempts.exists():
            scores = [attempt.score for attempt in completed_attempts]
            self.total_participants = len(scores)
            self.average_score = sum(scores) / len(scores)
            self.highest_score = max(scores)
        else:
            self.total_participants = 0
            self.average_score = 0.0
            self.highest_score = 0.0
        
        self.save()

class Question(models.Model):
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]
    
    exam_session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='multiple_choice'
    )
    
    # For multiple choice questions
    options = models.JSONField(
        default=list,
        blank=True,
        help_text="List of options for multiple choice questions"
    )
    
    correct_answer = models.TextField(
        help_text="Correct answer or correct option index"
    )
    
    explanation = models.TextField(
        blank=True,
        help_text="Explanation for the correct answer"
    )
    
    marks = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        unique_together = ['exam_session', 'order']
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.question_type == 'multiple_choice' and not self.options:
            raise ValidationError("Multiple choice questions must have options")
        
        if self.question_type == 'multiple_choice' and self.options:
            try:
                correct_index = int(self.correct_answer)
                if correct_index < 0 or correct_index >= len(self.options):
                    raise ValidationError("Correct answer index is out of range")
            except ValueError:
                raise ValidationError("Correct answer must be a valid option index for multiple choice")

class ExamAttempt(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='exam_attempts'
    )
    exam_session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name='exam_attempts'
    )
    
    # Timing
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    time_taken = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time taken in seconds"
    )
    
    # Answers stored as JSON
    answers = models.JSONField(
        default=dict,
        help_text="User answers in format {question_id: answer}"
    )
    
    # Scoring
    score = models.FloatField(default=0.0)
    percentage = models.FloatField(default=0.0)
    total_marks = models.IntegerField(default=0)
    
    # Status
    is_completed = models.BooleanField(default=False)
    is_submitted = models.BooleanField(default=False)
    
    # Payment (for paid exams)
    payment_id = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'exam_session']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.exam_session.title}"
    
    def calculate_score(self):
        """Calculate and update the score based on answers"""
        if not self.answers:
            return
        
        total_score = 0
        total_marks = 0
        
        for question in self.exam_session.questions.all():
            question_id = str(question.id)
            user_answer = self.answers.get(question_id)
            total_marks += question.marks
            
            if user_answer is not None:
                if self.is_answer_correct(question, user_answer):
                    total_score += question.marks
        
        self.score = total_score
        self.total_marks = total_marks
        self.percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
        self.save()
    
    def is_answer_correct(self, question, user_answer):
        """Check if user's answer is correct"""
        if question.question_type == 'multiple_choice':
            return str(user_answer) == question.correct_answer
        elif question.question_type == 'true_false':
            return str(user_answer).lower() == question.correct_answer.lower()
        elif question.question_type == 'short_answer':
            return user_answer.strip().lower() == question.correct_answer.strip().lower()
        # Essay questions need manual grading
        return False
    
    def submit_exam(self):
        """Submit the exam and calculate final score"""
        if not self.is_submitted:
            self.end_time = timezone.now()
            self.time_taken = int((self.end_time - self.start_time).total_seconds())
            self.is_completed = True
            self.is_submitted = True
            self.calculate_score()
            
            # Update exam statistics
            self.exam_session.update_statistics()
            
            # Update user profile statistics
            self.user.profile.update_statistics()

class ExamPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment gateway details
    payment_id = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
        ],
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'exam_session']
    
    def __str__(self):
        return f"{self.user.username} - {self.exam_session.title} - ${self.amount}"