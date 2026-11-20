from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('register/', views.RegisterView.as_view(), name='register'),

    path('contests/', views.ContestListView.as_view(), name='contest_list'),
    path('contests/<int:pk>/', views.ContestDetailView.as_view(), name='contest_detail'),
    path('contests/create/', views.ContestCreateView.as_view(), name='contest_create'),
    path('contests/<int:pk>/edit/', views.ContestUpdateView.as_view(), name='contest_edit'),
    path('contests/<int:pk>/delete/', views.ContestDeleteView.as_view(), name='contest_delete'),

    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_edit'),
    path('projects/<int:pk>/submit/', views.ProjectSubmitView.as_view(), name='project_submit'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    path('my-projects/', views.my_projects_view, name='my_projects'),

    path('evaluations/create/', views.EvaluationCreateView.as_view(), name='evaluation_create'),
    path('my-evaluations/', views.my_evaluations_view, name='my_evaluations'),

    path('export/projects/', views.export_projects_view, name='export_projects'),
    path('export/evaluations/', views.export_evaluations_view, name='export_evaluations'),

    path('projects/<int:pk>/vote/', views.vote_project, name='vote_project'),
    path('projects/<int:pk>/change-status/', views.change_status, name='change_status'),
    path('projects/<int:pk>/add-comment/', views.add_comment_ajax, name='add_comment_ajax'),
]