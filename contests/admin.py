from django.contrib import admin
from .models import (Contest, Stage, Project, Criterion, Evaluation, Comment,
                     Document, ProjectVote, Notification, StatusChange,
                     ExpertAssignment, TeamInvite, Achievement, UserAchievement)


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
    list_display = ['title', 'contest', 'participant', 'mentor', 'status', 'votes']
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

@admin.register(ProjectVote)
class ProjectVoteAdmin(admin.ModelAdmin):
    list_display = ['project', 'user', 'created_at']
    list_filter = ['user']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'text', 'is_read', 'created_at']
    list_filter = ['is_read']


@admin.register(StatusChange)
class StatusChangeAdmin(admin.ModelAdmin):
    list_display = ['project', 'old_status', 'new_status', 'changed_by', 'created_at']


@admin.register(ExpertAssignment)
class ExpertAssignmentAdmin(admin.ModelAdmin):
    list_display = ['project', 'expert', 'assigned_by', 'created_at']


@admin.register(TeamInvite)
class TeamInviteAdmin(admin.ModelAdmin):
    list_display = ['project', 'user', 'status', 'created_at']
    list_filter = ['status']


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'icon']


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ['user', 'achievement', 'earned_at']
