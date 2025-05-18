from django import forms
from django.forms import inlineformset_factory
from .models import Course, Module, Lesson, Quiz, Question, Option, Category, Content, Answer, Video

class CourseForm(forms.ModelForm):
    """
    Form for creating and updating courses.
    """
    class Meta:
        model = Course
        fields = [
            'title', 
            'overview',
            'description', 
            'category', 
            'difficulty', 
            'thumbnail', 
            'prerequisites', 
            'learning_outcomes',
            'price',
            'is_published'
        ]
        widgets = {
            'overview': forms.Textarea(attrs={'rows': 3, 'placeholder': 'A brief overview of the course'}),
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Detailed course description'}),
            'thumbnail': forms.FileInput(attrs={'class': 'form-control'}),
            'prerequisites': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Required prerequisites for this course'}),
            'learning_outcomes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What students will learn from this course'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Course price (0 for free)'}),
        }
        help_texts = {
            'overview': 'A short summary that appears in course listings.',
            'description': 'Detailed information about the course content and structure.',
            'is_published': 'Check this box to make the course visible to students.',
            'prerequisites': 'List any prerequisites or prior knowledge required for this course.',
            'learning_outcomes': 'List the key skills and knowledge students will gain.',
            'price': 'Set the course price (enter 0 for a free course).',
        }

class ModuleForm(forms.ModelForm):
    """
    Form for creating and editing course modules
    """
    class Meta:
        model = Module
        fields = ['title', 'description', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Module title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Module description'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Order in course (1, 2, 3...)'}),
        }

# Create a formset for adding multiple modules to a course
ModuleFormSet = inlineformset_factory(
    Course, 
    Module, 
    form=ModuleForm,
    fields=['title', 'description', 'order'],
    extra=1,  # Show 1 empty form by default
    can_delete=True,
    min_num=1,  # Require at least one module
    validate_min=True,
    max_num=20,  # Allow up to 20 modules
    validate_max=True,
    absolute_max=20
)

class ContentForm(forms.Form):
    CONTENT_TYPES = (
        ('video', 'Video'),
        ('lesson', 'Lesson'),
        ('quiz', 'Quiz'),
    )
    
    content_type = forms.ChoiceField(choices=CONTENT_TYPES)
    title = forms.CharField(max_length=200)
    order = forms.IntegerField(initial=0)
    
    # Video fields
    video_url = forms.URLField(required=False)
    
    # Lesson fields
    text_content = forms.CharField(widget=forms.Textarea, required=False)
    
    # Quiz fields
    description = forms.CharField(widget=forms.Textarea, required=False)
    time_limit = forms.IntegerField(initial=30, required=False)
    passing_score = forms.IntegerField(initial=70, required=False)
    
    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get('content_type')
        
        if content_type == 'video' and not cleaned_data.get('video_url'):
            raise forms.ValidationError('Video URL is required for video content')
        elif content_type == 'lesson' and not cleaned_data.get('text_content'):
            raise forms.ValidationError('Text content is required for lesson content')
        elif content_type == 'quiz' and not cleaned_data.get('description'):
            raise forms.ValidationError('Description is required for quiz content')
        
        return cleaned_data

class QuizForm(forms.ModelForm):
    """Form for creating and editing quizzes."""
    
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'time_limit', 'passing_score', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'time_limit': forms.NumberInput(attrs={'min': 1, 'max': 180}),
            'passing_score': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'order': forms.NumberInput(attrs={'min': 0})
        }
        help_texts = {
            'time_limit': 'Time limit in minutes (1-180)',
            'passing_score': 'Minimum score required to pass the quiz (0-100)',
            'order': 'Order in which this quiz appears in the module'
        }

class QuestionForm(forms.ModelForm):
    """
    Form for creating and editing quiz questions
    """
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'points']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Question text'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'points': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Points for this question'}),
        }

# Create a formset for adding multiple questions to a quiz
QuestionFormSet = inlineformset_factory(
    Quiz, 
    Question, 
    form=QuestionForm,
    extra=1,
    can_delete=True
)

class AnswerForm(forms.ModelForm):
    """
    Form for creating and editing answers to quiz questions
    """
    class Meta:
        model = Answer
        # Remove the explanation field that doesn't exist in the Answer model
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Answer text'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# Create a formset for adding multiple answers to a question
AnswerFormSet = inlineformset_factory(
    Question, 
    Answer, 
    form=AnswerForm,
    extra=4,
    can_delete=True
)

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'content', 'order']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10, 'class': 'rich-text-editor'}),
        }

class OptionForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
        }

# Create a formset for options
OptionFormSet = inlineformset_factory(
    Question, 
    Option,
    form=OptionForm,
    extra=4,
    can_delete=True,
    min_num=2,
    validate_min=True
) 