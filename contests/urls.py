from django.urls import path
from . import views
from .utils import import_projects_csv

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('roles/', views.RoleManagementView.as_view(), name='role_management'),

    path('contests/', views.ContestListView.as_view(), name='contest_list'),
    path('contests/create/', views.ContestCreateView.as_view(), name='contest_create'),
    path('contests/<int:pk>/', views.ContestDetailView.as_view(), name='contest_detail'),
    path('contests/<int:pk>/edit/', views.ContestUpdateView.as_view(), name='contest_edit'),
    path('contests/<int:pk>/delete/', views.ContestDeleteView.as_view(), name='contest_delete'),
    path('contests/<int:pk>/stages/add/', views.StageCreateView.as_view(), name='stage_add'),
    path('stages/<int:pk>/delete/', views.stage_delete, name='stage_delete'),
    path('contests/<int:pk>/criteria/add/', views.CriterionCreateView.as_view(), name='criterion_add'),
    path('criteria/<int:pk>/delete/', views.criterion_delete, name='criterion_delete'),

    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_edit'),
    path('projects/<int:pk>/submit/', views.ProjectSubmitView.as_view(), name='project_submit'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    path('projects/<int:pk>/vote/', views.vote_project, name='vote_project'),
    path('projects/<int:pk>/change-status/', views.change_status, name='change_status'),
    path('projects/<int:pk>/add-comment/', views.add_comment_ajax, name='add_comment_ajax'),
    path('projects/<int:pk>/assign-mentor/', views.assign_mentor, name='assign_mentor'),
    path('projects/<int:pk>/criteria.json', views.project_criteria_json, name='project_criteria_json'),
    path('projects/<int:pk>/documents/add/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),

    path('my-projects/', views.my_projects_view, name='my_projects'),
    path('my-evaluations/', views.my_evaluations_view, name='my_evaluations'),
    path('my-mentored/', views.my_mentored_view, name='my_mentored'),

    path('evaluations/create/', views.EvaluationCreateView.as_view(), name='evaluation_create'),

    path('export/projects/', views.export_projects_view, name='export_projects'),
    path('export/evaluations/', views.export_evaluations_view, name='export_evaluations'),
    path('import/projects/', import_projects_csv, name='import_projects'),
]
