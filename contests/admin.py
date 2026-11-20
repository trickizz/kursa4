from django.contrib import admin
from .models import Contest, Stage, Project, Criterion, Evaluation, Comment, Document


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_active', 'organizer']
    list_filter = ['is_active', 'start_date']
    search_fields = ['name', 'description']


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['name', 'contest', 'order', 'deadline']
    list_filter = ['contest']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'contest', 'participant', 'mentor', 'status']
    list_filter = ['status', 'contest']
    search_fields = ['title', 'summary']
    list_editable = ['status']


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ['name', 'contest', 'max_score']
    list_filter = ['contest']


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['project', 'expert', 'criterion', 'score']
    list_filter = ['expert', 'criterion']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['project', 'author', 'created_at']
    list_filter = ['author']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['project', 'description', 'uploaded_at']