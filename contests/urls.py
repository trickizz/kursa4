from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views
from . import api
from .utils import import_projects_csv

router = DefaultRouter()
router.register('contests', api.ContestViewSet)
router.register('projects', api.ProjectViewSet)
router.register('evaluations', api.EvaluationViewSet)

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('roles/', views.RoleManagementView.as_view(), name='role_management'),
    path('rating/', views.RatingView.as_view(), name='rating'),

    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/go/', views.notification_go, name='notification_go'),
    path('notifications/read-all/', views.notifications_read_all, name='notifications_read_all'),

    path('contests/', views.ContestListView.as_view(), name='contest_list'),
    path('contests/create/', views.ContestCreateView.as_view(), name='contest_create'),
    path('contests/<int:pk>/', views.ContestDetailView.as_view(), name='contest_detail'),
    path('contests/<int:pk>/edit/', views.ContestUpdateView.as_view(), name='contest_edit'),
    path('contests/<int:pk>/delete/', views.ContestDeleteView.as_view(), name='contest_delete'),
    path('contests/<int:pk>/results/', views.ContestResultsView.as_view(), name='contest_results'),
    path('contests/<int:pk>/results/pdf/', views.contest_results_pdf, name='contest_results_pdf'),
    path('contests/<int:pk>/finalize/', views.contest_finalize, name='contest_finalize'),
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
    path('projects/<int:pk>/assign-expert/', views.assign_expert, name='assign_expert'),
    path('projects/<int:pk>/invite/', views.invite_team_member, name='invite_team_member'),
    path('projects/<int:pk>/criteria.json', views.project_criteria_json, name='project_criteria_json'),
    path('projects/<int:pk>/documents/add/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('expert-assignments/<int:pk>/delete/', views.unassign_expert, name='unassign_expert'),
    path('team-invites/<int:pk>/respond/', views.respond_team_invite, name='respond_team_invite'),

    path('my-projects/', views.my_projects_view, name='my_projects'),
    path('my-evaluations/', views.my_evaluations_view, name='my_evaluations'),
    path('my-mentored/', views.my_mentored_view, name='my_mentored'),
    path('evaluations/create/', views.EvaluationCreateView.as_view(), name='evaluation_create'),

    path('export/projects/', views.export_projects_view, name='export_projects'),
    path('export/evaluations/', views.export_evaluations_view, name='export_evaluations'),
    path('import/projects/', import_projects_csv, name='import_projects'),

    path('api/', include(router.urls)),
    path('api/me/', api.MeView.as_view(), name='api_me'),
    path('api/token/', obtain_auth_token, name='api_token'),
    path('api/schema/', SpectacularAPIView.as_view(), name='api_schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api_schema'), name='api_docs'),
]
