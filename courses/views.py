from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, Http404
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.utils.translation import gettext as _
from django.utils.text import slugify
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
import json
from datetime import datetime, timedelta
import random
from django.forms import inlineformset_factory
import re

from .models import (
    Category, Course, Module, Lesson, Video, Quiz,
    Question, Option, Answer, Enrollment, Progress, QuizAttempt,
    PersonalizedQuizAttempt, Content, StudyPreference, StudySession, Deadline, FocusArea, StudyStreak, StudyGoal, QuizAnswer
)
from gamification.models import PointsTransaction, Achievement, UserAchievement, UserBadge
from .forms import (
    CourseForm, ModuleForm, ModuleFormSet, ContentForm, 
    QuizForm, QuestionForm, QuestionFormSet, AnswerForm, AnswerFormSet
)
from accounts.models import CustomUser, UserActivity


class CourseListView(ListView):
    """
    Display a list of all published courses.
    """
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 9
    
    def get_queryset(self):
        queryset = Course.objects.filter(is_published=True)
        
        # Filter by category if provided
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by search query if provided
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(overview__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by difficulty if provided
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['selected_category'] = self.kwargs.get('category_slug')
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
        return context


class CourseDetailView(DetailView):
    """
    Display details of a specific course.
    """
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        
        # Check if user is enrolled
        if self.request.user.is_authenticated:
            context['is_enrolled'] = Enrollment.objects.filter(
                student=self.request.user,
                course=course
            ).exists()
        else:
            context['is_enrolled'] = False
        
        # Get course modules and their content counts
        modules = course.modules.all().annotate(
            lesson_count=Count('lessons'),
            video_count=Count('videos'),
            quiz_count=Count('quizzes')
        )
        context['modules'] = modules
        
        # Get total content count
        context['total_lessons'] = sum(m.lesson_count for m in modules)
        context['total_videos'] = sum(m.video_count for m in modules)
        context['total_quizzes'] = sum(m.quiz_count for m in modules)
        
        return context


@login_required
def enroll_course(request, slug):
    course = get_object_or_404(Course, slug=slug)
    
    # Check if user is already enrolled
    if Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.info(request, f"You are already enrolled in {course.title}")
        return redirect('courses:course_detail', slug=slug)
    
    # Check if user is the instructor of this course
    if request.user == course.instructor:
        messages.warning(request, "You cannot enroll in your own course")
        return redirect('courses:course_detail', slug=slug)
    
    # Create enrollment
    enrollment = Enrollment.objects.create(
        student=request.user,
        course=course,
        status='enrolled'
    )
    
    # Award points for enrolling
    PointsTransaction.objects.create(
        user=request.user,
        points=10,  # Adjust point value as needed
        transaction_type='earned',
        description=f"Enrolled in course: {course.title}"
    )
    
    # Record user activity
    UserActivity.objects.create(
        user=request.user,
        activity_type='course_enrollment',
        content_type=ContentType.objects.get_for_model(course),
        object_id=course.id,
        data={'message': f"Enrolled in course: {course.title}"}
    )
    
    # Check for first enrollment achievement
    enrollment_count = Enrollment.objects.filter(student=request.user).count()
    if enrollment_count == 1:
        try:
            achievement = Achievement.objects.get(name="First Course Enrollment")
            UserAchievement.objects.get_or_create(
                user=request.user,
                achievement=achievement
            )
        except Achievement.DoesNotExist:
            pass  # Achievement doesn't exist yet
    
    messages.success(request, f"You have successfully enrolled in {course.title}! You earned 10 points.")
    return redirect('courses:course_detail', slug=slug)


@login_required
def my_courses(request):
    """
    View for displaying the student's enrolled courses.
    """
    enrolled_courses = Enrollment.objects.filter(
        student=request.user
    ).select_related('course').order_by('-enrolled_at')
    
    # Count completed courses
    completed_courses_count = enrolled_courses.filter(status='completed').count()
    
    # Calculate progress for each enrollment
    for enrollment in enrolled_courses:
        # Get all modules in the course
        modules = enrollment.course.modules.all()
        total_modules = modules.count()
        
        if total_modules == 0:
            enrollment.progress = 0
            continue
            
        # Get progress records for this course
        progress_records = Progress.objects.filter(
            student=request.user,
            course=enrollment.course
        )
        
        # Calculate overall course progress
        completed_modules = 0
        total_progress = 0
        
        for module in modules:
            try:
                progress = progress_records.get(module=module)
                total_progress += progress.completion_percentage
                if progress.completion_percentage == 100:
                    completed_modules += 1
                    
            except Progress.DoesNotExist:
                pass
        
        if total_modules > 0:
            if total_progress > 0:
                enrollment.progress = int(total_progress / total_modules)
            else:
                enrollment.progress = 0
            
        if enrollment.status == 'completed':
            enrollment.progress = 100
    
    context = {
        'enrolled_courses': enrolled_courses,
        'completed_courses_count': completed_courses_count
    }
    
    return render(request, 'courses/my_courses.html', context)


@login_required
def course_content(request, slug):
    """
    Display course content for enrolled students.
    """
    course = get_object_or_404(Course, slug=slug)
    
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    
    modules = course.modules.all().prefetch_related('lessons', 'videos', 'quizzes')
    
    progress_records = Progress.objects.filter(
        student=request.user,
        course=course
    )
    
    progress_dict = {p.module_id: p for p in progress_records}
    total_contents = 0
    completed_contents = 0
    next_content = None
    next_quiz = None
    all_quizzes_completed = True
    
    for module in modules:
        module_total = module.lessons.count() + module.videos.count() + module.quizzes.count()
        total_contents += module_total
        module_progress = progress_dict.get(module.id)
        module_completed = 0
        
        if module_progress:
            module_completed = (
                module_progress.completed_lessons.count() + 
                module_progress.completed_videos.count() + 
                module_progress.completed_quizzes.count()
            )
            completed_contents += module_completed
            
            # Check if module is completed
            module.is_completed = (module_completed == module_total and module_total > 0)
        else:
            module.is_completed = False
            
        # Find next content if not found yet
        if not next_content and module_completed < module_total:
            # Check lessons
            for lesson in module.lessons.all():
                if not module_progress or lesson not in module_progress.completed_lessons.all():
                    next_content = lesson
                    break
                    
            # Check videos if still no next content
            if not next_content:
                for video in module.videos.all():
                    if not module_progress or video not in module_progress.completed_videos.all():
                        next_content = video
                        break
            
            # Check quizzes for next quiz and all_quizzes_completed
            for quiz in module.quizzes.all():
                if not module_progress or quiz not in module_progress.completed_quizzes.all():
                    if not next_quiz:
                        next_quiz = quiz
                    all_quizzes_completed = False
    
    # Check if next_content exists and has an id
    if next_content and not hasattr(next_content, 'id'):
        next_content = None
        
    # Check if next_quiz exists and has an id
    if next_quiz and not hasattr(next_quiz, 'id'):
        next_quiz = None
    
    # Calculate overall progress percentage
    overall_progress = (completed_contents / total_contents * 100) if total_contents > 0 else 0
    
    context = {
        'course': course,
        'modules': modules,
        'enrollment': enrollment,
        'progress_dict': progress_dict,
        'overall_progress': overall_progress,
        'next_content': next_content,
        'next_quiz': next_quiz,
        'all_quizzes_completed': all_quizzes_completed
    }
    
    return render(request, 'courses/course_content.html', context)


@login_required
def lesson_detail(request, course_slug, lesson_id):
    """
    Display a specific lesson.
    """
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
    
    # Check if user is enrolled
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    
    # Get progress record for this module
    progress, created = Progress.objects.get_or_create(
        student=request.user,
        course=course,
        module=lesson.module
    )
    
    # Mark lesson as completed if not already
    if request.method == 'POST' and 'mark_completed' in request.POST:
        if lesson not in progress.completed_lessons.all():
            progress.completed_lessons.add(lesson)
            
            # Add points for completing a lesson (gamification)
            request.user.points += 10
            request.user.save()
            
            messages.success(request, f"Lesson marked as completed. +10 points!")
        
        return redirect('courses:lesson_detail', course_slug=course_slug, lesson_id=lesson_id)
    
    # Add debug information
    print(f"Course: {course.title}")
    print(f"Lesson: {lesson.title}")
    print(f"Content: {lesson.content[:100]}...")  # Print first 100 chars of content
    
    context = {
        'course': course,
        'lesson': lesson,
        'enrollment': enrollment,
        'progress': progress,
        'is_completed': lesson in progress.completed_lessons.all(),
        'debug_info': {
            'course_title': course.title,
            'lesson_title': lesson.title,
            'content_length': len(lesson.content) if lesson.content else 0,
            'module_title': lesson.module.title,
        }
    }
    
    return render(request, 'courses/lesson_detail.html', context)


@login_required
def video_detail(request, course_slug, video_id):
    """
    Display a specific video.
    """
    course = get_object_or_404(Course, slug=course_slug)
    video = get_object_or_404(Video, id=video_id, module__course=course)
    
    # Check if user is enrolled
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    
    # Get progress record for this module
    progress, created = Progress.objects.get_or_create(
        student=request.user,
        course=course,
        module=video.module
    )
    
    if request.method == 'POST' and 'mark_completed' in request.POST:
        if video not in progress.completed_videos.all():
            progress.completed_videos.add(video)
            request.user.points += 15
            request.user.save()
            
            messages.success(request, f"Video marked as completed. +15 points!")
        
        return redirect('courses:video_detail', course_slug=course_slug, video_id=video_id)
    
    context = {
        'course': course,
        'video': video,
        'enrollment': enrollment,
        'progress': progress,
        'is_completed': video in progress.completed_videos.all()
    }
    
    return render(request, 'courses/video_detail.html', context)


@login_required
def quiz_detail(request, course_slug, quiz_id):
    """
    Display a specific quiz.
    """
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, id=quiz_id, module__course=course)
    
    # Check if user is enrolled
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    
    # Get progress record for this module
    progress, created = Progress.objects.get_or_create(
        student=request.user,
        course=course,
        module=quiz.module
    )
    
    # Check if quiz is already completed
    is_completed = quiz in progress.completed_quizzes.all()
    
    # Get previous attempts - Changed 'student' to 'user'
    previous_attempts = QuizAttempt.objects.filter(
        user=request.user,
        quiz=quiz
    ).order_by('-started_at')
    
    context = {
        'course': course,
        'quiz': quiz,
        'enrollment': enrollment,
        'progress': progress,
        'is_completed': is_completed,
        'previous_attempts': previous_attempts,
        'questions': quiz.questions.all().prefetch_related('answers')
    }
    
    return render(request, 'courses/quiz_detail.html', context)


@login_required
def submit_quiz(request, course_slug, quiz_id):
    """
    Process quiz submission and calculate score.
    """
    if request.method != 'POST':
        return redirect('courses:quiz_detail', course_slug=course_slug, quiz_id=quiz_id)
    
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, id=quiz_id, module__course=course)
    
    # Get all questions for this quiz
    questions = quiz.questions.all()
    
    # Calculate score
    score = 0
    max_score = sum(q.points for q in questions)
    
    for question in questions:
        # Get the submitted answer(s)
        if question.question_type == 'multiple_choice':
            answer_id = request.POST.get(f'question_{question.id}')
            if answer_id:
                answer = get_object_or_404(Answer, id=answer_id, question=question)
                if answer.is_correct:
                    score += question.points
        elif question.question_type == 'true_false':
            answer_id = request.POST.get(f'question_{question.id}')
            if answer_id:
                answer = get_object_or_404(Answer, id=answer_id, question=question)
                if answer.is_correct:
                    score += question.points
        elif question.question_type == 'short_answer':
            # For short answer, we'll need to implement more sophisticated checking
            # This is a simplified version
            user_answer = request.POST.get(f'question_{question.id}', '').strip().lower()
            correct_answers = [a.text.strip().lower() for a in question.answers.filter(is_correct=True)]
            if user_answer in correct_answers:
                score += question.points
    
    # Calculate percentage score
    percentage_score = (score / max_score * 100) if max_score > 0 else 0
    
    # Determine if passed
    passed = percentage_score >= quiz.passing_score
    
    # Create quiz attempt record
    attempt = QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        score=score,
        max_score=max_score,
        completed_at=timezone.now(),
        passed=passed
    )
    
    # If passed, mark quiz as completed in progress
    if passed:
        progress = get_object_or_404(Progress, student=request.user, course=course, module=quiz.module)
        progress.completed_quizzes.add(quiz)
        
        # Add points for completing a quiz (gamification)
        points_earned = 25 + int(percentage_score / 4)  # Base points + bonus based on score
        request.user.points += points_earned
        request.user.save()
        
        messages.success(request, f"Quiz completed successfully! You earned {points_earned} points!")
    else:
        messages.warning(request, f"You didn't pass the quiz. Required: {quiz.passing_score}%, Your score: {int(percentage_score)}%")
    
    return redirect('courses:quiz_result', course_slug=course_slug, quiz_id=quiz_id, attempt_id=attempt.id)


@login_required
def quiz_result(request, course_slug, quiz_id, attempt_id):
    """
    Display quiz results.
    """
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, id=quiz_id, module__course=course)
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user, quiz=quiz)
    
    context = {
        'course': course,
        'quiz': quiz,
        'attempt': attempt,
        'score_percentage': attempt.score_percentage,
        'passed': attempt.passed
    }
    
    return render(request, 'courses/quiz_result.html', context)


@login_required
def generate_personalized_quiz(request, course_id=None):
    """
    Generate a personalized quiz based on user's weak areas.
    """
    user = request.user
    
    if not user.is_student:
        messages.error(request, "Only students can access personalized quizzes.")
        return redirect('accounts:dashboard')
    
    # Get user's quiz attempts to identify weak areas
    quiz_attempts = QuizAttempt.objects.filter(user=user)
    
    # If no quiz attempts, redirect to regular quizzes
    if not quiz_attempts.exists():
        messages.info(request, "Complete some quizzes first to get personalized challenges.")
        if course_id:
            return redirect('courses:course_detail', slug=Course.objects.get(id=course_id).slug)
        return redirect('courses:course_list')
    
    # Identify weak topics based on quiz performance
    weak_topics = []
    for attempt in quiz_attempts:
        if attempt.score < 70:  # Consider topics with score below 70% as weak
            weak_topics.append(attempt.quiz.module.id)
    
    # If no weak topics found, use topics with lowest scores
    if not weak_topics:
        lowest_score_attempts = quiz_attempts.order_by('score')[:3]
        weak_topics = [attempt.quiz.module.id for attempt in lowest_score_attempts]
    
    # Get questions from weak topics
    questions = []
    if course_id:
        # If course_id is provided, get questions only from that course
        questions = Question.objects.filter(
            quiz__module__course_id=course_id,
            quiz__module__id__in=weak_topics
        ).order_by('?')[:10]  # Randomly select 10 questions
    else:
        # Otherwise, get questions from all weak topics
        questions = Question.objects.filter(
            quiz__module__id__in=weak_topics
        ).order_by('?')[:10]  # Randomly select 10 questions
    
    # If not enough questions found, get random questions
    if questions.count() < 5:
        if course_id:
            additional_questions = Question.objects.filter(
                quiz__module__course_id=course_id
            ).exclude(id__in=[q.id for q in questions]).order_by('?')[:10-questions.count()]
            questions = list(questions) + list(additional_questions)
        else:
            additional_questions = Question.objects.all().exclude(
                id__in=[q.id for q in questions]
            ).order_by('?')[:10-questions.count()]
            questions = list(questions) + list(additional_questions)
    
    # Create a personalized quiz in the database
    from django.utils.text import slugify
    
    # Create a title for the personalized quiz
    title = f"Personalized Quiz for {user.username}"
    course = None
    if course_id:
        course = Course.objects.get(id=course_id)
        title = f"Personalized Quiz: {course.title}"
    
    # Get a default module to assign the quiz to
    default_module = None
    if course:
        default_module = course.modules.first()
    else:
        # If no specific course, get the first module from any course
        default_module = Module.objects.first()
    
    if not default_module:
        messages.error(request, "Unable to create a quiz: no modules available.")
        return redirect('courses:course_list')
    
    # Create a new quiz object
    personalized_quiz = Quiz.objects.create(
        title=title,
        description="This quiz is tailored to help you improve in areas where you need practice.",
        time_limit=15,  # 15 minutes
        passing_score=70,
        module=default_module
    )
    
    # Add the questions to the quiz
    for q in questions:
        personalized_quiz.questions.add(q)
    
    # Record user activity
    UserActivity.objects.create(
        user=user,
        activity_type='personalized_quiz_generation',
        content_object=personalized_quiz
    )
    
    return redirect('courses:take_personalized_quiz', quiz_id=personalized_quiz.id)


@login_required
def take_personalized_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Record user activity
    UserActivity.objects.create(
        user=request.user,
        activity_type='personalized_quiz_attempt',
        content_object=quiz
    )
    
    if request.method == 'POST':
        # Process quiz submission
        score = 0
        correct_answers = 0
        total_questions = quiz.questions.count()
        
        for question in quiz.questions.all():
            # Get user's answer
            if question.question_type == 'multiple_choice':
                answer_id = request.POST.get(f'question_{question.id}')
                if answer_id:
                    selected_option = get_object_or_404(Option, id=answer_id)
                    if selected_option.is_correct:
                        score += question.points
                        correct_answers += 1
            elif question.question_type == 'true_false':
                answer = request.POST.get(f'question_{question.id}')
                correct_answer = question.options.filter(is_correct=True).first()
                if answer and correct_answer and answer == str(correct_answer.id):
                    score += question.points
                    correct_answers += 1
            elif question.question_type == 'short_answer':
                user_answer = request.POST.get(f'question_{question.id}', '').strip().lower()
                correct_option = question.options.filter(is_correct=True).first()
                if correct_option and user_answer == correct_option.text.strip().lower():
                    score += question.points
                    correct_answers += 1
        
        # Create personalized quiz attempt record
        attempt = PersonalizedQuizAttempt.objects.create(
            user=request.user,
            title=f"Personalized Quiz: {quiz.title}",
            score=score,
            total_questions=total_questions,
            correct_answers=correct_answers
        )
        
        # Award points for completing personalized quiz
        PointsTransaction.objects.create(
            user=request.user,
            points=15,  # Adjust point value as needed
            transaction_type='earned',
            description=f"Completed personalized quiz: {quiz.title}"
        )
        
        # Check for achievements
        personalized_quizzes_taken = PersonalizedQuizAttempt.objects.filter(
            user=request.user
        ).count()
        
        # Example: Award achievement for taking first personalized quiz
        if personalized_quizzes_taken == 1:
            try:
                achievement = Achievement.objects.get(name="First Personalized Quiz")
                UserAchievement.objects.get_or_create(
                    user=request.user,
                    achievement=achievement
                )
            except Achievement.DoesNotExist:
                pass  # Achievement doesn't exist yet
        
        return redirect('courses:personalized_quiz_results', quiz_id=quiz_id)
    
    # Display quiz
    # Get all questions for this quiz with their answers
    questions = quiz.questions.all().prefetch_related('answers').order_by('?')[:10]  # Randomize and limit to 10 questions

    total_points = sum(question.points for question in questions)
    
    course = quiz.module.course
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'time_limit_seconds': quiz.time_limit * 60,
        'course': course,
        'is_personalized': True
    }
    
    # Use the existing quiz_detail.html template temporarily
    return render(request, 'courses/quiz_detail.html', context)


@login_required
def personalized_quiz_results(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Get the latest attempt
    attempt = PersonalizedQuizAttempt.objects.filter(
        user=request.user,
        title__contains=quiz.title
    ).order_by('-created_at').first()
    
    if not attempt:
        messages.error(request, "No attempt found for this quiz.")
        return redirect('courses:course_list')
    
    # Calculate percentage score
    percentage_score = (attempt.correct_answers / attempt.total_questions * 100) if attempt.total_questions > 0 else 0
    
    # Generate some feedback based on score
    if percentage_score >= 80:
        feedback = "Excellent work! You've demonstrated a strong understanding of these concepts."
    elif percentage_score >= 60:
        feedback = "Good job! You're making progress, but there's still room for improvement."
    else:
        feedback = "You need more practice with these concepts. Focus on reviewing the material."
    
    # Get course from quiz's module
    course = quiz.module.course
    
    context = {
        'quiz': quiz,
        'attempt': attempt,
        'score_percentage': percentage_score,
        'passed': percentage_score >= 70,  # Assuming 70% is passing
        'feedback': feedback,
        'course': course
    }
    
    # Use the existing quiz_result.html template
    return render(request, 'courses/quiz_result.html', context)


@login_required
def quiz_results(request, course_slug, quiz_id):
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Get the latest attempt
    attempt = QuizAttempt.objects.filter(
        user=request.user,
        quiz=quiz
    ).order_by('-completed_at').first()
    
    if not attempt:
        messages.warning(request, "You haven't taken this quiz yet")
        return redirect('courses:take_quiz', course_slug=course_slug, quiz_id=quiz_id)
    
    context = {
        'course': course,
        'quiz': quiz,
        'attempt': attempt,
        'percentage_score': (attempt.score / attempt.max_score * 100) if attempt.max_score > 0 else 0,
        'module': quiz.module,
    }
    
    return render(request, 'courses/quiz_results.html', context)


class CourseCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'
    
    def test_func(self):
        return self.request.user.is_instructor
    
    def form_valid(self, form):
        form.instance.instructor = self.request.user
        
        # Generate a base slug from the title
        base_slug = slugify(form.instance.title)
        
        # Check if the slug already exists
        slug = base_slug
        counter = 1
        
        while Course.objects.filter(slug=slug).exists():
            # If slug exists, append a number to make it unique
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        form.instance.slug = slug
        messages.success(self.request, f'Course "{form.instance.title}" has been created!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('courses:course_detail', kwargs={'slug': self.object.slug})


class ModuleListView(LoginRequiredMixin, ListView):
    model = Module
    template_name = 'courses/module_list.html'
    context_object_name = 'modules'
    
    def get_queryset(self):
        self.course = get_object_or_404(Course, slug=self.kwargs['slug'])
        return Module.objects.filter(course=self.course).order_by('order')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.course
        return context


class ModuleDetailView(LoginRequiredMixin, DetailView):
    model = Module
    template_name = 'courses/module_detail.html'
    context_object_name = 'module'
    
    def get_object(self):
        course_slug = self.kwargs.get('course_slug')
        module_id = self.kwargs.get('module_id')
        course = get_object_or_404(Course, slug=course_slug)
        return get_object_or_404(Module, course=course, id=module_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.object.course
        context['lessons'] = self.object.lessons.all().order_by('order')
        context['quizzes'] = self.object.quizzes.all()
        
        # Get previous and next modules
        all_modules = list(Module.objects.filter(course=self.object.course).order_by('order'))
        current_index = all_modules.index(self.object)
        
        if current_index > 0:
            context['prev_module'] = all_modules[current_index - 1]
        if current_index < len(all_modules) - 1:
            context['next_module'] = all_modules[current_index + 1]
        
        # Check if user has completed this module
        if self.request.user.is_authenticated:
            progress, created = Progress.objects.get_or_create(
                student=self.request.user,
                course=self.object.course,
                module=self.object
            )
            context['progress'] = progress
            
            # Record user activity
            UserActivity.objects.create(
                user=self.request.user,
                activity_type='module_view',
                content_object=self.object
            )
        
        return context 


@login_required
def complete_module(request, course_slug, module_id):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    
    # Get or create progress record
    progress, created = Progress.objects.get_or_create(
        student=request.user,
        course=course,
        module=module
    )
    
    # Check if all lessons and quizzes are completed
    lessons = module.lessons.all()
    quizzes = module.quizzes.all()
    
    all_completed = True
    
    # Check lessons
    for lesson in lessons:
        if lesson not in progress.completed_lessons.all():
            all_completed = False
            break
    
    # Check quizzes
    if all_completed:
        for quiz in quizzes:
            if quiz not in progress.completed_quizzes.all():
                all_completed = False
                break
    
    if all_completed:
        # Award points for completing the module
        PointsTransaction.objects.create(
            user=request.user,
            points=50,  # Adjust point value as needed
            transaction_type='earned',
            description=f"Completed module: {module.title}"
        )
        
        # Check for achievements
        modules_completed = Progress.objects.filter(
            student=request.user,
            completion_percentage=100
        ).count()
        
        # Example: Award achievement for completing first module
        if modules_completed == 1:
            achievement = Achievement.objects.get(name="First Module Completed")
            UserAchievement.objects.get_or_create(
                user=request.user,
                achievement=achievement
            )
        
        messages.success(request, f"Congratulations! You've completed the module '{module.title}' and earned 50 points!")
    else:
        messages.warning(request, "You need to complete all lessons and quizzes to mark this module as complete.")
    
    return redirect('courses:module_detail', course_slug=course_slug, module_id=module_id)


@login_required
def take_quiz(request, quiz_id):
    """
    View for taking a quiz.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    user = request.user
    
    # Check if the user is enrolled in the course
    if user not in quiz.module.course.students.all():
        return redirect('course_detail', slug=quiz.module.course.slug)
    
    # Check if the user has already started this quiz
    active_attempt = QuizAttempt.objects.filter(
        user=user,
        quiz=quiz,
        completed=False
    ).first()
    
    # Calculate total points from questions
    total_points = sum(question.points for question in quiz.questions.all())
    
    if not active_attempt:
        # Create a new quiz attempt
        active_attempt = QuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            max_score=total_points
        )
    
    # Get all questions for this quiz with their answers
    questions = Question.objects.filter(quiz=quiz).prefetch_related('answers').order_by('order')
    
    # Add debug information
    print(f"Quiz: {quiz.title}")
    print(f"Questions count: {questions.count()}")
    for q in questions:
        print(f"Question: {q.text}")
        print(f"Answers count: {q.answers.count()}")
    
    if request.method == 'POST':
        # Process quiz submission
        for question in questions:
            answer_id = request.POST.get(f'question_{question.id}')
            
            if answer_id:
                answer = Answer.objects.get(id=answer_id)
                
                # Check if the user has already answered this question
                quiz_answer = QuizAnswer.objects.filter(
                    quiz_attempt=active_attempt,
                    question=question
                ).first()
                
                if quiz_answer:
                    # Update existing answer
                    quiz_answer.answer = answer
                    quiz_answer.is_correct = answer.is_correct
                    quiz_answer.save()
                else:
                    # Create new answer
                    QuizAnswer.objects.create(
                        quiz_attempt=active_attempt,
                        question=question,
                        answer=answer,
                        is_correct=answer.is_correct
                    )
        
        # Check if the user wants to submit the quiz
        if 'submit_quiz' in request.POST:
            # Calculate score
            correct_answers = QuizAnswer.objects.filter(
                quiz_attempt=active_attempt,
                is_correct=True
            ).count()
            
            total_questions = questions.count()
            score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
            
            # Update quiz attempt
            active_attempt.score = correct_answers * (total_points / total_questions) if total_questions > 0 else 0
            active_attempt.completed = True
            active_attempt.completed_at = datetime.now()
            active_attempt.passed = score_percentage >= quiz.passing_score
            active_attempt.save()
            
            return redirect('courses:quiz_result', course_slug=quiz.module.course.slug, quiz_id=quiz.id, attempt_id=active_attempt.id)
    
    # Get user's answers for this attempt
    user_answers = {}
    for answer in QuizAnswer.objects.filter(quiz_attempt=active_attempt):
        user_answers[answer.question.id] = answer.answer.id if answer.answer else None
    
    # Prepare context
    context = {
        'quiz': quiz,
        'questions': questions,
        'user_answers': user_answers,
        'attempt': active_attempt,
        'content': quiz,  # Add the quiz as content for the template
        'debug_info': {
            'quiz_title': quiz.title,
            'questions_count': questions.count(),
            'has_questions': questions.exists(),
        }
    }
    
    return render(request, 'courses/content_types/quiz_take.html', context)


@login_required
def add_study_session(request):
    """
    View to add a new study session.
    """
    if request.method == 'POST':
        user = request.user
        title = request.POST.get('title')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        duration = request.POST.get('duration')
        priority = request.POST.get('priority')
        notes = request.POST.get('notes', '')
        course_id = request.POST.get('course')
        
        try:
            # Parse date and time
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            
            # Get course if provided
            course = None
            if course_id:
                course = Course.objects.get(id=course_id)
            
            # Create study session
            session = StudySession.objects.create(
                user=user,
                title=title,
                date=date,
                start_time=start_time,
                duration=int(duration),
                priority=priority,
                notes=notes,
                course=course
            )
            
            return JsonResponse({'success': True, 'session_id': session.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def update_study_session(request, session_id):
    """
    View to update an existing study session.
    """
    if request.method == 'POST':
        try:
            session = StudySession.objects.get(id=session_id, user=request.user)
            
            # Update fields if provided
            if 'title' in request.POST:
                session.title = request.POST.get('title')
            if 'date' in request.POST:
                session.date = datetime.strptime(request.POST.get('date'), '%Y-%m-%d').date()
            if 'start_time' in request.POST:
                session.start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            if 'duration' in request.POST:
                session.duration = int(request.POST.get('duration'))
            if 'priority' in request.POST:
                session.priority = request.POST.get('priority')
            if 'notes' in request.POST:
                session.notes = request.POST.get('notes')
            if 'completed' in request.POST:
                session.completed = request.POST.get('completed') == 'true'
            if 'course' in request.POST and request.POST.get('course'):
                session.course = Course.objects.get(id=request.POST.get('course'))
            
            session.save()
            
            # Update streak if session is completed
            if session.completed:
                streak, created = StudyStreak.objects.get_or_create(user=request.user)
                streak.update_streak(session.date)
            
            return JsonResponse({'success': True})
        except StudySession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_study_session(request, session_id):
    """
    View to delete a study session.
    """
    if request.method == 'POST':
        try:
            session = StudySession.objects.get(id=session_id, user=request.user)
            session.delete()
            return JsonResponse({'success': True})
        except StudySession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def update_study_preferences(request):
    """
    View to update study preferences.
    """
    if request.method == 'POST':
        try:
            preferences, created = StudyPreference.objects.get_or_create(user=request.user)
            
            # Update fields if provided
            if 'daily_goal' in request.POST:
                preferences.daily_goal = float(request.POST.get('daily_goal'))
            if 'weekly_goal' in request.POST:
                preferences.weekly_goal = float(request.POST.get('weekly_goal'))
            if 'preferred_time' in request.POST:
                preferences.preferred_time = request.POST.get('preferred_time')
            if 'session_length' in request.POST:
                preferences.session_length = request.POST.get('session_length')
            if 'email_notifications' in request.POST:
                preferences.email_notifications = request.POST.get('email_notifications') == 'true'
            if 'browser_notifications' in request.POST:
                preferences.browser_notifications = request.POST.get('browser_notifications') == 'true'
            if 'reminder_notifications' in request.POST:
                preferences.reminder_notifications = request.POST.get('reminder_notifications') == 'true'
            
            preferences.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def add_deadline(request):
    """
    View to add a new deadline.
    """
    if request.method == 'POST':
        user = request.user
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        due_date_str = request.POST.get('due_date')
        course_id = request.POST.get('course')
        
        try:
            # Parse due date
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            
            # Get course if provided
            course = None
            if course_id:
                course = Course.objects.get(id=course_id)
            
            # Create deadline
            deadline = Deadline.objects.create(
                user=user,
                title=title,
                description=description,
                due_date=due_date,
                course=course
            )
            
            return JsonResponse({'success': True, 'deadline_id': deadline.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def update_deadline(request, deadline_id):
    """
    View to update an existing deadline.
    """
    if request.method == 'POST':
        try:
            deadline = Deadline.objects.get(id=deadline_id, user=request.user)
            
            # Update fields if provided
            if 'title' in request.POST:
                deadline.title = request.POST.get('title')
            if 'description' in request.POST:
                deadline.description = request.POST.get('description')
            if 'due_date' in request.POST:
                deadline.due_date = datetime.strptime(request.POST.get('due_date'), '%Y-%m-%d').date()
            if 'completed' in request.POST:
                deadline.completed = request.POST.get('completed') == 'true'
            if 'course' in request.POST and request.POST.get('course'):
                deadline.course = Course.objects.get(id=request.POST.get('course'))
            
            deadline.save()
            
            return JsonResponse({'success': True})
        except Deadline.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Deadline not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_deadline(request, deadline_id):
    """
    View to delete a deadline.
    """
    if request.method == 'POST':
        try:
            deadline = Deadline.objects.get(id=deadline_id, user=request.user)
            deadline.delete()
            return JsonResponse({'success': True})
        except Deadline.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Deadline not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def add_focus_area(request):
    """
    View to add a new focus area.
    """
    if request.method == 'POST':
        user = request.user
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        
        try:
            # Create focus area
            focus_area = FocusArea.objects.create(
                user=user,
                title=title,
                description=description
            )
            
            return JsonResponse({'success': True, 'focus_area_id': focus_area.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def update_focus_area(request, focus_area_id):
    """
    View to update an existing focus area.
    """
    if request.method == 'POST':
        try:
            focus_area = FocusArea.objects.get(id=focus_area_id, user=request.user)
            
            # Update fields if provided
            if 'title' in request.POST:
                focus_area.title = request.POST.get('title')
            if 'description' in request.POST:
                focus_area.description = request.POST.get('description')
            if 'progress' in request.POST:
                focus_area.progress = int(request.POST.get('progress'))
            if 'hours_spent' in request.POST:
                focus_area.hours_spent = float(request.POST.get('hours_spent'))
            
            focus_area.save()
            
            return JsonResponse({'success': True})
        except FocusArea.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Focus area not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_focus_area(request, focus_area_id):
    """
    View to delete a focus area.
    """
    if request.method == 'POST':
        try:
            focus_area = FocusArea.objects.get(id=focus_area_id, user=request.user)
            focus_area.delete()
            return JsonResponse({'success': True})
        except FocusArea.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Focus area not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def add_study_goal(request):
    """
    View to add a new study goal.
    """
    if request.method == 'POST':
        user = request.user
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        target_date_str = request.POST.get('target_date', '')
        
        try:
            # Parse target date if provided
            target_date = None
            if target_date_str:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            
            # Create study goal
            goal = StudyGoal.objects.create(
                user=user,
                title=title,
                description=description,
                target_date=target_date
            )
            
            return JsonResponse({'success': True, 'goal_id': goal.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def update_study_goal(request, goal_id):
    """
    View to update an existing study goal.
    """
    if request.method == 'POST':
        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
            
            # Update fields if provided
            if 'title' in request.POST:
                goal.title = request.POST.get('title')
            if 'description' in request.POST:
                goal.description = request.POST.get('description')
            if 'target_date' in request.POST and request.POST.get('target_date'):
                goal.target_date = datetime.strptime(request.POST.get('target_date'), '%Y-%m-%d').date()
            if 'progress' in request.POST:
                goal.progress = int(request.POST.get('progress'))
            
            goal.save()
            
            return JsonResponse({'success': True})
        except StudyGoal.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Study goal not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_study_goal(request, goal_id):
    """
    View to delete a study goal.
    """
    if request.method == 'POST':
        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
            goal.delete()
            return JsonResponse({'success': True})
        except StudyGoal.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Study goal not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def personalized_recommendations(request):
    """
    View for the personalized recommendations page.
    """
    user = request.user
    
    # Get user's enrolled courses
    enrolled_courses = Course.objects.filter(students=user)
    
    # Get user's completed quizzes
    completed_quizzes = QuizAttempt.objects.filter(
        user=user,
        completed=True
    ).select_related('quiz__module__course')
    
    # Get user's study sessions
    study_sessions = StudySession.objects.filter(
        user=user,
        completed=True
    ).select_related('course')
    
    # Calculate learning statistics
    total_courses = enrolled_courses.count()
    completed_courses = enrolled_courses.filter(progress=100).count()
    in_progress_courses = total_courses - completed_courses
    
    total_quizzes = completed_quizzes.count()
    avg_quiz_score = completed_quizzes.aggregate(Avg('score'))['score__avg'] or 0
    
    total_study_hours = sum(session.duration for session in study_sessions) / 60
    
    # Get focus areas
    focus_areas = FocusArea.objects.filter(user=user).order_by('-hours_spent')[:5]
    
    # Get study goals
    study_goals = StudyGoal.objects.filter(user=user).order_by('target_date')
    
    # Identify skill gaps based on quiz performance
    skill_gaps = []
    low_scoring_quizzes = completed_quizzes.filter(score__lt=70)
    
    for quiz_attempt in low_scoring_quizzes:
        quiz = quiz_attempt.quiz
        course = quiz.module.course
        
        # Check if this skill gap is already in the list
        if not any(gap['skill'] == quiz.title for gap in skill_gaps):
            skill_gaps.append({
                'skill': quiz.title,
                'course': course.title,
                'score': quiz_attempt.score,
                'last_attempt': quiz_attempt.completed_at
            })
    
    # Sort skill gaps by score (ascending)
    skill_gaps = sorted(skill_gaps, key=lambda x: x['score'])[:5]
    
    # Get recommended courses
    # For simplicity, we'll recommend courses that the user is not enrolled in
    # In a real implementation, this would use more sophisticated recommendation algorithms
    recommended_courses = Course.objects.exclude(
        id__in=enrolled_courses.values_list('id', flat=True)
    ).filter(
        is_published=True
    ).order_by('-created_at')[:6]
    
    # Prepare context
    context = {
        'learning_statistics': {
            'total_courses': total_courses,
            'completed_courses': completed_courses,
            'in_progress_courses': in_progress_courses,
            'total_quizzes': total_quizzes,
            'avg_quiz_score': avg_quiz_score,
            'total_study_hours': total_study_hours,
        },
        'skill_gaps': skill_gaps,
        'focus_areas': focus_areas,
        'study_goals': study_goals,
        'recommended_courses': recommended_courses,
    }
    
    return render(request, 'courses/personalized_recommendations.html', context)


@login_required
def learning_path(request):
    """
    View for the learning path page.
    """
    user = request.user
    
    # Get user's enrolled courses
    enrolled_courses = Course.objects.filter(students=user).order_by('created_at')
    
    # Get user's study goals
    study_goals = StudyGoal.objects.filter(user=user).order_by('target_date')
    
    # Get user's focus areas
    focus_areas = FocusArea.objects.filter(user=user).order_by('-hours_spent')
    
    # Calculate overall progress
    total_courses = enrolled_courses.count()
    completed_courses = enrolled_courses.filter(progress=100).count()
    overall_progress = (completed_courses / total_courses * 100) if total_courses > 0 else 0
    
    # Estimate completion date based on current progress and study rate
    # For simplicity, we'll use a fixed rate of 1 course per month
    remaining_courses = total_courses - completed_courses
    months_to_complete = remaining_courses
    estimated_completion_date = datetime.now() + timedelta(days=30 * months_to_complete)
    
    # Organize courses into learning path modules
    # For simplicity, we'll group courses by category or create artificial groupings
    learning_modules = []
    
    # Group courses by category
    course_categories = {}
    for course in enrolled_courses:
        category = course.category if hasattr(course, 'category') and course.category else "General"
        if category not in course_categories:
            course_categories[category] = []
        course_categories[category].append(course)
    
    # Create learning modules from categories
    for category, courses in course_categories.items():
        # Calculate module progress
        total_module_courses = len(courses)
        completed_module_courses = len([c for c in courses if getattr(c, 'progress', 0) == 100])
        module_progress = (completed_module_courses / total_module_courses * 100) if total_module_courses > 0 else 0
        
        learning_modules.append({
            'title': f"{category} Skills",
            'description': f"Master the fundamentals of {category}",
            'completed': module_progress == 100,
            'progress': module_progress,
            'courses': courses,
        })
    
    # If no categories exist, create a default module
    if not learning_modules:
        total_module_courses = enrolled_courses.count()
        completed_module_courses = enrolled_courses.filter(progress=100).count()
        module_progress = (completed_module_courses / total_module_courses * 100) if total_module_courses > 0 else 0
        
        learning_modules.append({
            'title': "Your Learning Path",
            'description': "Complete these courses to achieve your learning goals",
            'completed': module_progress == 100,
            'progress': module_progress,
            'courses': enrolled_courses,
        })
    
    # Calculate milestones completed
    milestones_completed = completed_courses
    
    # Prepare context
    context = {
        'learning_goals': study_goals,
        'skills_progress': focus_areas,
        'path_overview': {
            'estimated_completion': estimated_completion_date.strftime('%B %d, %Y'),
            'total_courses': total_courses,
            'certificates': completed_courses,  # Assuming one certificate per completed course
            'total_hours': total_courses * 10,  # Assuming 10 hours per course on average
        },
        'learning_path': learning_modules,
        'path_completion': {
            'overall_progress': overall_progress,
            'milestones_completed': milestones_completed,
            'estimated_completion': estimated_completion_date.strftime('%B %d, %Y'),
        },
    }
    
    return render(request, 'courses/learning_path.html', context)


@login_required
def study_planner(request):
    """
    View for the study planner page.
    """
    user = request.user
    
    # Get or create study preferences
    preferences, created = StudyPreference.objects.get_or_create(user=user)
    
    # Get study sessions for the calendar
    study_sessions = StudySession.objects.filter(user=user)
    
    # Get today's study sessions
    today = datetime.now().date()
    today_sessions = study_sessions.filter(date=today).order_by('start_time')
    
    # Get upcoming deadlines
    upcoming_deadlines = Deadline.objects.filter(
        user=user, 
        due_date__gte=today,
        completed=False
    ).order_by('due_date')[:5]
    
    # Get focus areas
    focus_areas = FocusArea.objects.filter(user=user).order_by('-hours_spent')[:5]
    
    # Get or create study streak
    streak, created = StudyStreak.objects.get_or_create(user=user)
    
    # Calculate study statistics
    total_sessions = study_sessions.count()
    completed_sessions = study_sessions.filter(completed=True).count()
    completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Calculate total study hours this week
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    this_week_sessions = study_sessions.filter(
        date__gte=start_of_week,
        date__lte=end_of_week,
        completed=True
    )
    weekly_hours = sum(session.duration for session in this_week_sessions) / 60
    weekly_goal_progress = (weekly_hours / preferences.weekly_goal * 100) if preferences.weekly_goal > 0 else 0
    
    # Calculate total study hours today
    today_completed_sessions = today_sessions.filter(completed=True)
    daily_hours = sum(session.duration for session in today_completed_sessions) / 60
    daily_goal_progress = (daily_hours / preferences.daily_goal * 100) if preferences.daily_goal > 0 else 0
    
    # Prepare calendar data
    calendar_data = []
    for session in study_sessions:
        calendar_data.append({
            'id': session.id,
            'title': session.title,
            'start': f"{session.date.isoformat()}T{session.start_time.isoformat()}",
            'end': f"{session.date.isoformat()}T{session.end_time.isoformat()}",
            'className': f"priority-{session.priority} {'completed' if session.completed else ''}",
            'extendedProps': {
                'course': session.course.title if session.course else None,
                'notes': session.notes,
                'priority': session.priority,
                'completed': session.completed,
            }
        })
    
    # Prepare context
    context = {
        'preferences': preferences,
        'today_sessions': today_sessions,
        'upcoming_deadlines': upcoming_deadlines,
        'focus_areas': focus_areas,
        'streak': streak,
        'study_statistics': {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'completion_rate': completion_rate,
            'weekly_hours': weekly_hours,
            'weekly_goal': preferences.weekly_goal,
            'weekly_goal_progress': weekly_goal_progress,
            'daily_hours': daily_hours,
            'daily_goal': preferences.daily_goal,
            'daily_goal_progress': daily_goal_progress,
        },
        'calendar_data': json.dumps(calendar_data),
    }
    
    return render(request, 'courses/study_planner.html', context)


@login_required
def view_content(request, content_id):
    """
    View for displaying different types of content (lesson, video, quiz).
    """
    # Try to find the content in different content types
    content = None
    content_type = None
    
    # Check if it's a lesson
    try:
        content = Lesson.objects.get(id=content_id)
        content_type = 'lesson'
    except Lesson.DoesNotExist:
        pass
    
    # Check if it's a video
    if not content:
        try:
            content = Video.objects.get(id=content_id)
            content_type = 'video'
        except Video.DoesNotExist:
            pass
    
    # Check if it's a quiz
    if not content:
        try:
            content = Quiz.objects.get(id=content_id)
            content_type = 'quiz'
        except Quiz.DoesNotExist:
            pass
    
    # If content not found, return 404
    if not content:
        raise Http404("Content not found")
    
    # Get the course and module
    module = content.module
    course = module.course
    
    # Check if user is enrolled in the course
    if request.user not in course.students.all():
        return redirect('courses:course_detail', slug=course.slug)
    
    # Render appropriate template based on content type
    if content_type == 'lesson':
        return render(request, 'courses/content_types/lesson.html', {
            'lesson': content,
            'course': course,
            'module': module
        })
    elif content_type == 'video':
        return render(request, 'courses/content_types/video.html', {
            'video': content,
            'course': course,
            'module': module
        })
    elif content_type == 'quiz':
        return render(request, 'courses/content_types/quiz_intro.html', {
            'quiz': content,
            'course': course,
            'module': module
        })


@login_required
def instructor_dashboard(request):
    """
    View for the instructor dashboard.
    """
    # Check if user is an instructor
    if not request.user.is_staff and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Get courses created by the instructor
    courses = Course.objects.filter(instructor=request.user)
    
    # Get total number of students enrolled in all courses
    total_students = sum(course.students.count() for course in courses)
    
    # Get total number of modules across all courses
    total_modules = sum(course.modules.count() for course in courses)
    
    # Get total number of quizzes across all courses
    total_quizzes = 0
    for course in courses:
        for module in course.modules.all():
            total_quizzes += module.quizzes.count()
    
    # Get recent enrollments
    recent_enrollments = Enrollment.objects.filter(
        course__instructor=request.user
    ).order_by('-enrolled_at')[:10]
    
    # Get recent quiz attempts
    recent_quiz_attempts = QuizAttempt.objects.filter(
        quiz__module__course__instructor=request.user
    ).order_by('-completed_at')[:10]
    
    # Prepare context
    context = {
        'courses': courses,
        'total_students': total_students,
        'total_modules': total_modules,
        'total_quizzes': total_quizzes,
        'recent_enrollments': recent_enrollments,
        'recent_quiz_attempts': recent_quiz_attempts,
    }
    
    return render(request, 'courses/instructor/dashboard.html', context)


@login_required
def instructor_courses(request):
    """
    View for displaying courses created by the instructor.
    """
    # Check if user is an instructor
    if not request.user.is_staff and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Get courses created by the instructor
    courses = Course.objects.filter(instructor=request.user).order_by('-created_at')
    
    # Prepare context
    context = {
        'courses': courses,
    }
    
    return render(request, 'courses/instructor/courses.html', context)


@login_required
def edit_course(request, course_id):
    """
    View for editing a course.
    """
    # Get the course
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user is the instructor of the course
    if request.user != course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Handle form submission
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Course "{course.title}" has been updated successfully!')
            return redirect('courses:instructor_courses')
    else:
        form = CourseForm(instance=course)
    
    # Prepare context
    context = {
        'form': form,
        'course': course,
    }
    
    return render(request, 'courses/instructor/course_form.html', context)


@login_required
def edit_course_modules(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user is the instructor
    if request.user != course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    ModuleFormSet = inlineformset_factory(
        Course,
        Module,
        fields=['title', 'description', 'order'],
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        formset = ModuleFormSet(request.POST, instance=course)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Modules updated successfully!')
            return redirect('courses:course_detail', slug=course.slug)
    else:
        formset = ModuleFormSet(instance=course)
    
    return render(request, 'courses/instructor/module_formset.html', {
        'course': course,
        'formset': formset
    })


@login_required
def delete_course(request, course_id):
    """
    View for deleting a course.
    """
    # Get the course
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user is the instructor of the course
    if request.user != course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Handle form submission
    if request.method == 'POST':
        course.delete()
        return redirect('courses:instructor_courses')
    
    # Prepare context
    context = {
        'course': course,
    }
    
    return render(request, 'courses/instructor/course_confirm_delete.html', context)


@login_required
def module_content_list(request, module_id):
    """
    View for displaying content of a module.
    """
    # Get the module
    module = get_object_or_404(Module, id=module_id)
    
    # Check if user is the instructor of the course
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Prepare context
    context = {
        'module': module,
    }
    
    return render(request, 'courses/instructor/module_content_list.html', context)


@login_required
def add_module_content(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = ContentForm(request.POST)
        if form.is_valid():
            content_type = form.cleaned_data['content_type']
            
            if content_type == 'video':
                video = Video.objects.create(
                    module=module,
                    title=form.cleaned_data['title'],
                    order=form.cleaned_data['order'],
                    url=form.cleaned_data['video_url']
                )
                messages.success(request, 'Video content added successfully!')
                return redirect('courses:module_content_list', module_id=module.id)
                
            elif content_type == 'lesson':
                lesson = Lesson.objects.create(
                    module=module,
                    title=form.cleaned_data['title'],
                    order=form.cleaned_data['order'],
                    content=form.cleaned_data['text_content']
                )
                messages.success(request, 'Lesson content added successfully!')
                return redirect('courses:module_content_list', module_id=module.id)
                
            elif content_type == 'quiz':
                # For quiz, redirect to the quiz creation form with initial data
                return redirect(
                    f"/courses/instructor/module/{module_id}/quiz/create/?title={form.cleaned_data['title']}&description={form.cleaned_data['description']}&order={form.cleaned_data['order']}"
                )
    else:
        form = ContentForm()
    
    return render(request, 'courses/instructor/add_content.html', {
        'form': form,
        'module': module
    })


@login_required
def create_quiz(request, module_id):
    """Create a new quiz."""
    module = get_object_or_404(Module, id=module_id)
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.module = module
            quiz.save()
            
            # Process questions and answers
            questions_data = {}
            deleted_questions = request.POST.getlist('deleted_questions[]')
            
            # Delete questions marked for deletion
            if deleted_questions:
                Question.objects.filter(id__in=deleted_questions).delete()
            
            # Process form data to get questions
            for key, value in request.POST.items():
                if key.startswith('questions['):
                    # Extract question ID/key and field name
                    match = re.match(r'questions\[(new_\d+|\d+)\]\[(\w+)\](?:\[\])?', key)
                    if match:
                        q_id, field = match.groups()
                        if q_id not in questions_data:
                            questions_data[q_id] = {
                                'title': '',
                                'text': '',
                                'points': 1,
                                'order': 0,
                                'answers': [],
                                'correct_answer': 0
                            }
                        
                        if field == 'answers':
                            questions_data[q_id]['answers'].append(value)
                        else:
                            questions_data[q_id][field] = value
            
            # Create or update questions
            for q_id, data in questions_data.items():
                if not data.get('text') or not data.get('answers'):
                    continue
                
                if q_id.startswith('new_'):
                    # Create new question
                    question = Question.objects.create(
                        quiz=quiz,
                        title=data['title'],
                        text=data['text'],
                        points=data['points'],
                        order=data['order']
                    )
                else:
                    # Update existing question
                    question = Question.objects.get(id=q_id)
                    question.title = data['title']
                    question.text = data['text']
                    question.points = data['points']
                    question.order = data['order']
                    question.save()
                    # Delete existing answers
                    question.answers.all().delete()
                
                # Create answers for the question
                correct_answer_idx = int(data.get('correct_answer', 0))
                
                # Print debug information about answers
                print(f"Creating answers for question: {question.text}")
                print(f"Answer data: {data['answers']}")
                print(f"Correct answer index: {correct_answer_idx}")
                
                for idx, answer_text in enumerate(data['answers']):
                    if answer_text.strip():  # Only create answers with non-empty text
                        Answer.objects.create(
                            question=question,
                            text=answer_text,
                            is_correct=(idx == correct_answer_idx)
                        )
                        print(f"Created answer {idx+1}: {answer_text} (correct: {idx == correct_answer_idx})")
                
                # Verify answers were created
                print(f"Answer count after creation: {question.answers.count()}")
            
            messages.success(request, 'Quiz created successfully!')
            return redirect('courses:module_content_list', module_id=module.id)
    else:
        # Get initial data from query parameters
        initial_data = {
            'title': request.GET.get('title', ''),
            'description': request.GET.get('description', ''),
            'order': request.GET.get('order', 0)
        }
        form = QuizForm(initial=initial_data)
    
    return render(request, 'courses/instructor/quiz_form.html', {
        'form': form,
        'module': module
    })


@login_required
def edit_quiz(request, quiz_id):
    """Edit an existing quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    module = quiz.module
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            quiz = form.save()
            
            # Process questions and answers
            questions_data = {}
            deleted_questions = request.POST.getlist('deleted_questions[]')
            
            # Delete questions marked for deletion
            if deleted_questions:
                Question.objects.filter(id__in=deleted_questions).delete()
            
            # Process form data to get questions
            for key, value in request.POST.items():
                if key.startswith('questions['):
                    # Extract question ID/key and field name
                    match = re.match(r'questions\[(new_\d+|\d+)\]\[(\w+)\](?:\[\])?', key)
                    if match:
                        q_id, field = match.groups()
                        if q_id not in questions_data:
                            questions_data[q_id] = {
                                'title': '',
                                'text': '',
                                'points': 1,
                                'order': 0,
                                'answers': [],
                                'correct_answer': 0
                            }
                        
                        if field == 'answers':
                            questions_data[q_id]['answers'].append(value)
                        else:
                            questions_data[q_id][field] = value
            
            # Create or update questions
            for q_id, data in questions_data.items():
                if not data.get('text') or not data.get('answers'):
                    continue
                
                if q_id.startswith('new_'):
                    # Create new question
                    question = Question.objects.create(
                        quiz=quiz,
                        title=data['title'],
                        text=data['text'],
                        points=data['points'],
                        order=data['order']
                    )
                else:
                    # Update existing question
                    question = Question.objects.get(id=q_id)
                    question.title = data['title']
                    question.text = data['text']
                    question.points = data['points']
                    question.order = data['order']
                    question.save()
                    # Delete existing answers
                    question.answers.all().delete()
                
                # Create answers for the question
                correct_answer_idx = int(data.get('correct_answer', 0))
                
                # Print debug information about answers
                print(f"Creating answers for question: {question.text}")
                print(f"Answer data: {data['answers']}")
                print(f"Correct answer index: {correct_answer_idx}")
                
                for idx, answer_text in enumerate(data['answers']):
                    if answer_text.strip():  # Only create answers with non-empty text
                        Answer.objects.create(
                            question=question,
                            text=answer_text,
                            is_correct=(idx == correct_answer_idx)
                        )
                        print(f"Created answer {idx+1}: {answer_text} (correct: {idx == correct_answer_idx})")
                
                # Verify answers were created
                print(f"Answer count after creation: {question.answers.count()}")
            
            messages.success(request, 'Quiz updated successfully!')
            return redirect('courses:module_content_list', module_id=module.id)
    else:
        form = QuizForm(instance=quiz)
    
    return render(request, 'courses/instructor/quiz_form.html', {
        'form': form,
        'quiz': quiz,
        'module': module
    })


@login_required
def quiz_questions_list(request, quiz_id):
    """
    View for displaying questions of a quiz.
    """
    # Get the quiz
    quiz = get_object_or_404(Quiz, id=quiz_id)
    module = quiz.module
    course = module.course
    
    # Check if user is the instructor of the course
    if request.user != quiz.module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Prepare context
    context = {
        'quiz': quiz,
        'questions': quiz.questions.all().order_by('order'),
        'module': module,
        'course': course,
    }
    
    return render(request, 'courses/instructor/quiz_questions_list.html', context)


@login_required
def add_quiz_questions(request, quiz_id):
    """
    View for adding questions to a quiz.
    """
    # Get the quiz
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Check if user is the instructor of the course
    if request.user != quiz.module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Handle form submission
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()
            return redirect('courses:add_question_answers', question_id=question.id)
    else:
        form = QuestionForm()
    
    # Prepare context
    context = {
        'form': form,
        'quiz': quiz,
    }
    
    return render(request, 'courses/instructor/question_form.html', context)


@login_required
def add_question_answers(request, question_id):
    """
    View for adding answers to a question.
    """
    # Get the question
    question = get_object_or_404(Question, id=question_id)
    
    # Check if user is the instructor of the course
    if request.user != question.quiz.module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    # Handle form submission
    if request.method == 'POST':
        formset = AnswerFormSet(request.POST, instance=question)
        
        if formset.is_valid():
            answers = formset.save(commit=False)
            
            # Get the correct answer index
            correct_answer_index = request.POST.get('correct_answer')
            
            # Set is_correct flag for each answer
            for i, answer in enumerate(answers):
                answer.is_correct = (str(i) == correct_answer_index)
                answer.save()
                
            # Handle deleted forms
            formset.save_m2m()
            
            # Debug information
            print(f"Saved answers for question: {question.text}")
            print(f"Total answers: {question.answers.count()}")
            for ans in question.answers.all():
                print(f"Answer: {ans.text}, Correct: {ans.is_correct}")
            
            messages.success(request, "Answers saved successfully!")
            return redirect('courses:quiz_questions_list', quiz_id=question.quiz.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        formset = AnswerFormSet(instance=question)
        
        # If no answers exist yet, create at least 4 empty forms
        if question.answers.count() == 0:
            formset.extra = 4
    
    # Prepare context
    context = {
        'formset': formset,
        'question': question,
    }
    
    return render(request, 'courses/instructor/answer_formset.html', context)


@login_required
def edit_lesson(request, lesson_id):
    """Edit a lesson."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    module = lesson.module
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = ContentForm(request.POST)
        if form.is_valid():
            lesson.title = form.cleaned_data['title']
            lesson.content = form.cleaned_data['text_content']
            lesson.order = form.cleaned_data['order']
            lesson.save()
            messages.success(request, 'Lesson updated successfully!')
            return redirect('courses:module_content_list', module_id=module.id)
    else:
        form = ContentForm(initial={
            'content_type': 'lesson',
            'title': lesson.title,
            'text_content': lesson.content,
            'order': lesson.order
        })
    
    return render(request, 'courses/instructor/edit_content.html', {
        'form': form,
        'module': module,
        'content': lesson,
        'content_type': 'lesson'
    })


@login_required
def edit_video(request, video_id):
    """Edit a video."""
    video = get_object_or_404(Video, id=video_id)
    module = video.module
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = ContentForm(request.POST)
        if form.is_valid():
            video.title = form.cleaned_data['title']
            video.url = form.cleaned_data['video_url']
            video.order = form.cleaned_data['order']
            video.save()
            messages.success(request, 'Video updated successfully!')
            return redirect('courses:module_content_list', module_id=module.id)
    else:
        form = ContentForm(initial={
            'content_type': 'video',
            'title': video.title,
            'video_url': video.url,
            'order': video.order
        })
    
    return render(request, 'courses/instructor/edit_content.html', {
        'form': form,
        'module': module,
        'content': video,
        'content_type': 'video'
    })


@login_required
def edit_quiz(request, quiz_id):
    """Edit a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    module = quiz.module
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = ContentForm(request.POST)
        if form.is_valid():
            quiz.title = form.cleaned_data['title']
            quiz.description = form.cleaned_data['description']
            quiz.order = form.cleaned_data['order']
            quiz.time_limit = form.cleaned_data['time_limit']
            quiz.passing_score = form.cleaned_data['passing_score']
            quiz.save()
            messages.success(request, 'Quiz updated successfully!')
            return redirect('courses:module_content_list', module_id=module.id)
    else:
        form = ContentForm(initial={
            'content_type': 'quiz',
            'title': quiz.title,
            'description': quiz.description,
            'order': quiz.order,
            'time_limit': quiz.time_limit,
            'passing_score': quiz.passing_score
        })
    
    return render(request, 'courses/instructor/edit_content.html', {
        'form': form,
        'module': module,
        'content': quiz,
        'content_type': 'quiz'
    })


@login_required
def delete_lesson(request, lesson_id):
    """Delete a lesson."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    module = lesson.module
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, 'Lesson deleted successfully!')
        return redirect('courses:module_content_list', module_id=module.id)
    
    return render(request, 'courses/instructor/delete_content.html', {
        'module': module,
        'content': lesson,
        'content_type': 'lesson'
    })


@login_required
def delete_video(request, video_id):
    """Delete a video."""
    video = get_object_or_404(Video, id=video_id)
    module = video.module
    
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        video.delete()
        messages.success(request, 'Video deleted successfully!')
        return redirect('courses:module_content_list', module_id=module.id)
    
    return render(request, 'courses/instructor/delete_content.html', {
        'module': module,
        'content': video,
        'content_type': 'video'
    })


@login_required
def delete_quiz(request, quiz_id):
    """Delete a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    module = quiz.module
    
    # Check if user is the instructor
    if request.user != module.course.instructor and not request.user.is_superuser:
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, 'Quiz deleted successfully!')
        return redirect('courses:module_content_list', module_id=module.id)
    
    return render(request, 'courses/instructor/delete_content.html', {
        'module': module,
        'content': quiz,
        'content_type': 'quiz'
    }) 