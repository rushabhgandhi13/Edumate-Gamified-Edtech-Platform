from django.contrib import admin
from .models import (
    Category, Course, Module, Lesson, Video, Quiz,
    Question, Answer, Option, Enrollment, Progress, QuizAttempt,
    PersonalizedQuizAttempt, QuizAnswer,
    StudySession, StudyGoal, StudyPreference, StudyStreak, Deadline, FocusArea
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


class ModuleInline(admin.StackedInline):
    model = Module
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'difficulty', 'created_at', 'is_published']
    list_filter = ['is_published', 'difficulty', 'category', 'created_at']
    search_fields = ['title', 'overview', 'description']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    inlines = [ModuleInline]


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1


class VideoInline(admin.StackedInline):
    model = Video
    extra = 1


class QuizInline(admin.StackedInline):
    model = Quiz
    extra = 1


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order']
    list_filter = ['course']
    search_fields = ['title', 'description']
    inlines = [LessonInline, VideoInline, QuizInline]


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'question_type', 'points', 'order']
    list_filter = ['quiz', 'question_type']
    search_fields = ['text']
    inlines = [AnswerInline, OptionInline]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'time_limit', 'passing_score']
    list_filter = ['module', 'time_limit', 'passing_score']
    search_fields = ['title', 'description']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'enrolled_at', 'status']
    list_filter = ['status', 'enrolled_at']
    search_fields = ['student__username', 'course__title']
    date_hierarchy = 'enrolled_at'


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'module', 'last_accessed', 'completion_percentage']
    list_filter = ['course', 'module', 'last_accessed']
    search_fields = ['student__username', 'course__title', 'module__title']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'score', 'max_score', 'score_percentage', 'passed', 'completed_at']
    list_filter = ['passed', 'started_at', 'completed_at']
    search_fields = ['user__username', 'quiz__title']
    date_hierarchy = 'started_at'


@admin.register(PersonalizedQuizAttempt)
class PersonalizedQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'score', 'total_questions', 'correct_answers', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'title']
    date_hierarchy = 'created_at'


# Register remaining models
admin.site.register(Lesson)
admin.site.register(Video)
admin.site.register(Answer)
admin.site.register(Option)
# Remove Content registration since it's an abstract model
admin.site.register(QuizAnswer)
admin.site.register(StudySession)
admin.site.register(StudyGoal)
admin.site.register(StudyPreference)
admin.site.register(StudyStreak)
admin.site.register(Deadline)
admin.site.register(FocusArea) 