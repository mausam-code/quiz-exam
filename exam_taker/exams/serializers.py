from rest_framework import serializers
from .models import ExamSession, Question, ExamAttempt, ExamPayment
from accounts.serializers import UserProfileSerializer

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type', 'options',
            'marks', 'order', 'explanation'
        ]
        # Don't expose correct_answer in API responses
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Only include correct_answer for exam creators or after exam completion
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            # Show correct answer to exam creator or after user completes exam
            if (user == instance.exam_session.created_by or 
                instance.exam_session.exam_attempts.filter(user=user, is_completed=True).exists()):
                data['correct_answer'] = instance.correct_answer
        return data

class QuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'options',
            'correct_answer', 'explanation', 'marks', 'order'
        ]
    
    def validate(self, data):
        if data['question_type'] == 'multiple_choice':
            if not data.get('options'):
                raise serializers.ValidationError("Multiple choice questions must have options")
            
            try:
                correct_index = int(data['correct_answer'])
                if correct_index < 0 or correct_index >= len(data['options']):
                    raise serializers.ValidationError("Correct answer index is out of range")
            except (ValueError, TypeError):
                raise serializers.ValidationError("Correct answer must be a valid option index")
        
        return data

class ExamSessionSerializer(serializers.ModelSerializer):
    created_by = UserProfileSerializer(read_only=True)
    questions_count = serializers.SerializerMethodField()
    can_participate = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    is_finished = serializers.ReadOnlyField()
    participants_count = serializers.ReadOnlyField()
    
    class Meta:
        model = ExamSession
        fields = [
            'id', 'title', 'description', 'duration', 'is_paid', 'price',
            'start_time', 'end_time', 'max_participants', 'difficulty',
            'is_public', 'created_by', 'status', 'total_participants',
            'average_score', 'highest_score', 'created_at', 'updated_at',
            'questions_count', 'can_participate', 'is_active', 'is_upcoming',
            'is_finished', 'participants_count'
        ]
        read_only_fields = [
            'id', 'created_by', 'total_participants', 'average_score',
            'highest_score', 'created_at', 'updated_at'
        ]
    
    def get_questions_count(self, obj):
        return obj.questions.count()
    
    def get_can_participate(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            can_participate, message = obj.can_user_participate(request.user)
            return {'can_participate': can_participate, 'message': message}
        return {'can_participate': False, 'message': 'Authentication required'}

class ExamSessionCreateSerializer(serializers.ModelSerializer):
    questions = QuestionCreateSerializer(many=True, required=False)
    
    class Meta:
        model = ExamSession
        fields = [
            'title', 'description', 'duration', 'is_paid', 'price',
            'start_time', 'end_time', 'max_participants', 'difficulty',
            'is_public', 'questions'
        ]
    
    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        exam_session = ExamSession.objects.create(**validated_data)
        
        # Create questions
        for question_data in questions_data:
            Question.objects.create(exam_session=exam_session, **question_data)
        
        return exam_session
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        if data['is_paid'] and data['price'] <= 0:
            raise serializers.ValidationError("Paid exams must have a price greater than 0")
        
        return data

class ExamAttemptSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    exam_session = ExamSessionSerializer(read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'user', 'exam_session', 'start_time', 'end_time',
            'time_taken', 'score', 'percentage', 'total_marks',
            'is_completed', 'is_submitted', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'exam_session', 'start_time', 'end_time',
            'time_taken', 'score', 'percentage', 'total_marks',
            'is_completed', 'is_submitted', 'created_at'
        ]

class AnswerSubmissionSerializer(serializers.Serializer):
    answers = serializers.JSONField()
    
    def validate_answers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers must be a dictionary")
        return value

class ExamPaymentSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    exam_session = ExamSessionSerializer(read_only=True)
    
    class Meta:
        model = ExamPayment
        fields = [
            'id', 'user', 'exam_session', 'amount', 'payment_id',
            'payment_method', 'status', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'exam_session', 'created_at'
        ]