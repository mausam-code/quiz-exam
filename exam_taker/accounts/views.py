from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    UserProfileSerializer, UserStatsSerializer,
    TeacherRegistrationSerializer
)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        #Generate JWT tokens

        refresh = RefreshToken.for_user(user)

        return Response({
            'message':'User Registered Successfully',
            'user':UserProfileSerializer(user).data,
            'tokens':{
                'refresh':str(refresh),
                'access':str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
    
class LoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data= request.data)
        serializer.is_valid(raise_exception = True)

        user = serializer.validated_data['user']

        #Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'message':'Login Successful',
            'User':UserProfileSerializer(user).data,
            'tokens':{
                'refresh':str(refresh),
                'access':str(refresh.access_token),
            }
        })

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class UserStatsView(generics.RetrieveAPIView):
    serializer_class = UserStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        if not created:
            profile.update_statistics()
        return profile
    
class CreateTeacherView(generics.CreateAPIView):
    serializer_class = TeacherRegistrationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        #Only admins can create teachers
        if not self.request.user.is_admin_user:
            raise permissions.PermissionDenied("Only admins can create teacher accounts")
        
        serializer.save()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message':'Successfully logged out'}, status = status.HTTP_200_OK)
    except Exception as e:
        return Response({'error':str(e)}, status=status.HTTP_400_BAD_REQUEST)
