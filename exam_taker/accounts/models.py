from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

# Create your models here.
class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('normal','Normal User'),
        ('teacher','Teacher'),
        ('admin','Admin'),
    ]

    user_type = models.CharField(
        max_length = 10,
        choices = USER_TYPE_CHOICES,
        default='normal'
    )

    phone_regex = RegexValidator(
        regex = r'^\+?1?\d{9,15}$',
        message = "phone number must be entered in the format: '+977 9801234567'. up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex],max_length=17,blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True
    )

    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)

    #Additional fields for tracking
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username}({self.get_user_type_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name}{self.last_name}".strip()
    
    @property
    def is_admin_user(self):
        return self.user_type == 'admin'
    
    @property
    def is_normal_user(self):
        return self.user_type == 'normal'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    total_exams_taken = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    average_score = models.FloatField(default=0)
    rank = models.IntegerField(null=True, blank = True)

    #Subscription related Fields

    is_premium = models.BooleanField(default=False)
    premium_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-average_score']
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def update_statistics(self):
        """Update User Statistics based on exam attempts"""
        from exams.models import ExamAttempt

        attempts = ExamAttempt.objects.filter(
            user = self.user,
            is_completed = True
        )

        self.total_exams_taken = attempts.count()
        if self.total_exams_taken>0:
            self.total_score = sum(attempt.score for attempt in attempts)
            self.average_score = self.total_score/ self.total_exams_taken
        else:
            self.total_score = 0
            self.average_score=0.0
        
        self.save()
