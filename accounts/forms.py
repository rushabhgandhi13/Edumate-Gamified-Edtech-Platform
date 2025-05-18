from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

# Import models directly to avoid circular imports
from .models import CustomUser, UserProfile

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users with our custom fields.
    """
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    is_student = forms.BooleanField(required=False, initial=True, help_text=_("Register as a student"))
    is_instructor = forms.BooleanField(required=False, help_text=_("Register as an instructor"))
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'is_student', 'is_instructor')


class CustomUserChangeForm(UserChangeForm):
    """
    Form for updating users with our custom fields.
    """
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'bio', 'profile_picture', 
                  'date_of_birth')


class CustomSignupForm(forms.Form):
    """
    Custom signup form for django-allauth.
    """
    first_name = forms.CharField(max_length=30, label=_('First Name'))
    last_name = forms.CharField(max_length=30, label=_('Last Name'))
    is_student = forms.BooleanField(required=False, initial=True, label=_('I am a student'))
    is_instructor = forms.BooleanField(required=False, label=_('I am an instructor'))
    
    def save(self, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_student = self.cleaned_data.get('is_student', True)
        user.is_instructor = self.cleaned_data.get('is_instructor', False)
        user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """
    Form for updating user profile information.
    """
    class Meta:
        model = UserProfile
        fields = [
            'location', 
            'website', 
            'social_links', 
            'interests',
            'content_difficulty_preference',
            'email_notifications',
            'achievement_notifications',
            'reminder_notifications'
        ]
        widgets = {
            'social_links': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter as JSON: {"twitter": "username", "linkedin": "url"}'}),
            'interests': forms.TextInput(attrs={'placeholder': 'e.g., Programming, Data Science, Design'}),
        }


class UserRegistrationForm(UserCreationForm):
    """
    Form for user registration.
    """
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create user profile
            UserProfile.objects.create(user=user)
        
        return user


class UserUpdateForm(forms.ModelForm):
    """
    Form for updating user information.
    """
    email = forms.EmailField(max_length=254, required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


class ProfileUpdateForm(forms.ModelForm):
    """
    Form for updating user profile information.
    """
    class Meta:
        model = UserProfile
        fields = ['location', 'website', 'interests', 'content_difficulty_preference',
                 'email_notifications', 'achievement_notifications', 'reminder_notifications']
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'interests': forms.TextInput(attrs={'class': 'form-control'}),
            'content_difficulty_preference': forms.Select(attrs={'class': 'form-select'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'achievement_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SignUpForm(UserCreationForm):
    """
    Form for user registration
    """
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    user_type = forms.ChoiceField(
        choices=[('student', 'Student'), ('instructor', 'Instructor')],
        required=True,
        help_text='Select your role'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        # Set user type (student or instructor)
        user_type = self.cleaned_data['user_type']
        if user_type == 'instructor':
            user.is_instructor = True
        else:
            user.is_student = True
        
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """
    Form for updating user profile
    """
    class Meta:
        model = UserProfile
        fields = ('location', 'website', 'interests', 'content_difficulty_preference')
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'interests': forms.TextInput(attrs={'class': 'form-control'}),
            'content_difficulty_preference': forms.Select(attrs={'class': 'form-select'}),
        } 