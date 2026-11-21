from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.generic import (ListView, DetailView, CreateView, UpdateView,
                                  DeleteView, TemplateView, FormView)
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count, Q, Sum, Avg
from django.http import JsonResponse, Http404, HttpResponse, StreamingHttpResponse, FileResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.cache import cache
from django_ratelimit.decorators import ratelimit
import json
import os
import time
from django.conf import settings
from django.db import connection

from .models import (Contest, Project, Evaluation, Comment, Criterion, Stage,
                     Document, ProjectVote, Notification, StatusChange,
                     ExpertAssignment, TeamInvite, Achievement, UserAchievement,
                     Appeal, MentorTask, Tag, ResultSnapshot)
from .forms import (ContestForm, ProjectForm, ProjectSubmitForm, DocumentForm,
                    RegisterForm, EvaluationForm, StageForm, CriterionForm,
                    MentorAssignForm, ExpertAssignForm, TeamInviteForm,
                    RoleAssignForm, ImportCSVForm, AppealForm, AppealResolveForm,
                    MentorTaskForm, BulkActionForm)
from .mixins import (OrganizerRequiredMixin, ExpertRequiredMixin,
                     ParticipantRequiredMixin, AdminRequiredMixin)
from .roles import (is_site_admin, is_organizer, is_expert, primary_role,
                    set_role, ROLE_INFO, ALL_ROLES)
from .services import notify, set_project_status, award, parse_mentions
from .utils import export_projects_csv, export_evaluations_csv
from .pdf import generate_results_pdf


# ---------------------------------------------------------------- регистрация
class RegisterView(FormView):
    template_name = 'registration/register.html'
    form_class = RegisterForm
    success_url = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Регистрация прошла успешно! Теперь можно войти.')
        return super().form_valid(form)


# ------------------------------------------------------------------- публичное
class HomeView(ListView):
    model = Contest
    template_name = 'contests/home.html'
    context_object_name = 'contests'

    def get_queryset(self):
        return (Contest.objects.filter(is_active=True)
                .annotate(project_count=Count('projects')).order_by('-created_at')[:6])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = {
            'contests': Contest.objects.filter(is_active=True).count(),
            'projects': Project.objects.exclude(status='draft').count(),
            'members': User.objects.filter(is_active=True).count(),
            'evaluations': Evaluation.objects.count(),
        }
        return context


class ContestListView(ListView):
    model = Contest
    template_name = 'contests/contest_list.html'
    context_object_name = 'contests'
    paginate_by = 9

    def get_queryset(self):
        queryset = Contest.objects.annotate(project_count=Count('projects')).order_by('-created_at')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context


class ContestDetailView(DetailView):
    model = Contest
    template_name = 'contests/contest_detail.html'
    context_object_name = 'contest'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stages'] = self.object.stages.all().order_by('order')
        context['criteria'] = self.object.criteria.all()
        context['projects'] = self.object.projects.exclude(status='draft').select_related('participant', 'mentor')
        context['stage_form'] = StageForm()
        context['criterion_form'] = CriterionForm()
        context['today'] = timezone.localdate()
        return context


class ProjectListView(ListView):
    model = Project
    template_name = 'contests/project_list.html'
    context_object_name = 'projects'
    paginate_by = 9

    def get_queryset(self):
        queryset = (Project.objects.exclude(status='draft')
                    .select_related('contest', 'participant').order_by('-created_at'))
        contest_id = self.request.GET.get('contest')
        status = self.request.GET.get('status')
        query = self.request.GET.get('q', '').strip()
        if contest_id:
            queryset = queryset.filter(contest_id=contest_id)
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(summary__icontains=query))
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__name=tag)
        sort = self.request.GET.get('sort', 'new')
        if sort == 'votes':
            queryset = queryset.order_by('-votes')
        elif sort == 'old':
            queryset = queryset.order_by('created_at')
        elif sort == 'score':
            queryset = queryset.annotate(avg_score=Avg('evaluations__score')).order_by('-avg_score')
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contests'] = Contest.objects.all()
        context['status_choices'] = Project.STATUS_CHOICES
        context['current_contest'] = self.request.GET.get('contest', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['q'] = self.request.GET.get('q', '')
        context['tags'] = Tag.objects.all()
        context['current_tag'] = self.request.GET.get('tag', '')
        context['current_sort'] = self.request.GET.get('sort', 'new')
        return context


class ProjectDetailView(DetailView):
    model = Project
    template_name = 'contests/project_detail.html'
    context_object_name = 'project'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        if obj.status == 'draft' and not obj.is_member(user) and not is_organizer(user):
            raise Http404('Черновик недоступен')
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj, user = self.object, self.request.user
        can_manage = is_organizer(user)
        is_owner = user.is_authenticated and obj.participant_id == user.pk
        is_member = obj.is_member(user)

        context['evaluations'] = obj.evaluations.select_related('expert', 'criterion')
        context['comments'] = obj.comments.filter(parent__isnull=True).select_related('author').prefetch_related('replies__author')
        context['documents'] = obj.documents.all()
        context['status_history'] = obj.status_history.select_related('changed_by')[:12]
        context['team'] = obj.team.all()
        context['expert_assignments'] = obj.expert_assignments.select_related('expert')
        context['document_form'] = DocumentForm()
        context['mentor_form'] = MentorAssignForm(initial={'mentor': obj.mentor})
        context['expert_form'] = ExpertAssignForm(project=obj)
        context['team_form'] = TeamInviteForm(project=obj)
        context['status_choices'] = Project.STATUS_CHOICES
        context['user_voted'] = (user.is_authenticated and
                                 ProjectVote.objects.filter(project=obj, user=user).exists())
        context['tags'] = obj.tags.all()
        context['weighted_score'] = obj.weighted_score_percent()
        context['appeals'] = obj.appeals.select_related('author', 'evaluation__criterion')
        context['appeal_form'] = AppealForm()
        context['mentor_tasks'] = obj.mentor_tasks.all()
        context['mentor_task_form'] = MentorTaskForm()
        context['is_project_mentor'] = user.is_authenticated and obj.mentor_id == user.pk
        context['contest_locked'] = obj.contest.results_finalized
        context['is_owner'] = is_owner
        context['can_edit'] = (is_owner and obj.is_editable_by_participant()) or can_manage
        context['can_submit'] = is_owner and obj.is_editable_by_participant() and obj.contest.is_open
        context['can_delete'] = is_owner or can_manage
        context['can_upload'] = is_member or can_manage or (user.is_authenticated and obj.mentor_id == user.pk)
        context['can_evaluate'] = is_expert(user) and not is_member and obj.status != 'draft'
        context['score_percent'] = obj.score_percent()
        return context


# ------------------------------------------------------- конкурсы (организатор)
class ContestCreateView(LoginRequiredMixin, OrganizerRequiredMixin, CreateView):
    model = Contest
    form_class = ContestForm
    template_name = 'contests/contest_form.html'
    success_url = reverse_lazy('contest_list')

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        messages.success(self.request, 'Конкурс создан! Добавьте этапы и критерии на странице конкурса.')
        return super().form_valid(form)


class ContestUpdateView(LoginRequiredMixin, OrganizerRequiredMixin, UpdateView):
    model = Contest
    form_class = ContestForm
    template_name = 'contests/contest_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Конкурс обновлён.')
        return super().form_valid(form)


class ContestDeleteView(LoginRequiredMixin, OrganizerRequiredMixin, DeleteView):
    model = Contest
    template_name = 'contests/contest_confirm_delete.html'
    success_url = reverse_lazy('contest_list')

    def form_valid(self, form):
        messages.success(self.request, 'Конкурс удалён.')
        return super().form_valid(form)


class StageCreateView(LoginRequiredMixin, OrganizerRequiredMixin, CreateView):
    model = Stage
    form_class = StageForm
    template_name = 'contests/stage_criterion_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contest = get_object_or_404(Contest, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contest'] = self.contest
        context['form_title'] = f'Новый этап — {self.contest.name}'
        return context

    def form_valid(self, form):
        form.instance.contest = self.contest
        self.object = form.save()
        messages.success(self.request, 'Этап добавлен.')
        return redirect('contest_detail', pk=self.contest.pk)


@login_required
@require_POST
def stage_delete(request, pk):
    stage = get_object_or_404(Stage, pk=pk)
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав.')
        return redirect('home')
    contest_pk = stage.contest_id
    stage.delete()
    messages.success(request, 'Этап удалён.')
    return redirect('contest_detail', pk=contest_pk)


class CriterionCreateView(LoginRequiredMixin, OrganizerRequiredMixin, CreateView):
    model = Criterion
    form_class = CriterionForm
    template_name = 'contests/stage_criterion_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contest = get_object_or_404(Contest, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contest'] = self.contest
        context['form_title'] = f'Новый критерий — {self.contest.name}'
        return context

    def form_valid(self, form):
        form.instance.contest = self.contest
        self.object = form.save()
        messages.success(self.request, 'Критерий добавлен.')
        return redirect('contest_detail', pk=self.contest.pk)


@login_required
@require_POST
def criterion_delete(request, pk):
    criterion = get_object_or_404(Criterion, pk=pk)
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав.')
        return redirect('home')
    contest_pk = criterion.contest_id
    criterion.delete()
    messages.success(request, 'Критерий удалён.')
    return redirect('contest_detail', pk=contest_pk)


# --------------------------------------------------------- проекты (участник)
class ProjectCreateView(LoginRequiredMixin, ParticipantRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'contests/project_form.html'

    def form_valid(self, form):
        form.instance.participant = self.request.user
        response = super().form_valid(form)
        award(self.request.user, 'debut')
        messages.success(self.request, 'Проект создан как черновик. Загрузите документы и отправьте его на конкурс!')
        return response


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'contests/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        owner_ok = obj.participant == request.user and obj.is_editable_by_participant()
        if not (owner_ok or is_organizer(request.user)):
            messages.error(request, 'Редактировать может только автор (до подачи проекта) или организатор.')
            return redirect('project_detail', pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Проект обновлён.')
        return super().form_valid(form)


class ProjectSubmitView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectSubmitForm
    template_name = 'contests/project_submit.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.participant != request.user and not is_organizer(request.user):
            messages.error(request, 'Подать проект может только его автор.')
            return redirect('project_detail', pk=obj.pk)
        if not obj.is_editable_by_participant():
            messages.error(request, 'Этот проект уже подан на конкурс.')
            return redirect('project_detail', pk=obj.pk)
        if not obj.contest.is_open:
            messages.error(request, 'Приём заявок на этот конкурс закрыт.')
            return redirect('project_detail', pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        set_project_status(form.instance, 'submitted', self.request.user)
        award(self.request.user, 'submitted')
        messages.success(self.request, 'Проект отправлен на конкурс!')
        return redirect('project_detail', pk=form.instance.pk)


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Project
    template_name = 'contests/project_confirm_delete.html'
    success_url = reverse_lazy('project_list')

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.participant != request.user and not is_organizer(request.user):
            messages.error(request, 'Удалить проект может только его автор или организатор.')
            return redirect('project_detail', pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Проект удалён.')
        return super().form_valid(form)


# ------------------------------------------------------------------- документы
class DocumentUploadView(LoginRequiredMixin, FormView):
    form_class = DocumentForm
    template_name = 'contests/document_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, pk=kwargs['pk'])
        user = request.user
        allowed = self.project.is_member(user) or is_organizer(user) or self.project.mentor_id == user.pk
        if request.user.is_authenticated and not allowed:
            messages.error(request, 'Загружать документы могут автор, команда, наставник или организатор.')
            return redirect('project_detail', pk=self.project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        return context

    def form_valid(self, form):
        document = form.save(commit=False)
        document.project = self.project
        document.save()
        messages.success(self.request, 'Документ загружен.')
        return redirect('project_detail', pk=self.project.pk)


@login_required
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk)
    project = document.project
    if project.participant != request.user and not is_organizer(request.user):
        messages.error(request, 'Нет прав на удаление документа.')
        return redirect('project_detail', pk=project.pk)
    document.file.delete(save=False)
    document.delete()
    messages.success(request, 'Документ удалён.')
    return redirect('project_detail', pk=project.pk)


# -------------------------------------------------------------------- оценки
class EvaluationCreateView(LoginRequiredMixin, ExpertRequiredMixin, CreateView):
    model = Evaluation
    form_class = EvaluationForm
    template_name = 'contests/evaluation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['expert'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.request.GET.get('project')
        if project_id:
            initial['project'] = project_id
        return initial

    def form_valid(self, form):
        form.instance.expert = self.request.user
        response = super().form_valid(form)
        project = self.object.project
        notify(project.all_members(), self.request.user,
               f'Эксперт {self.request.user.username} оценил проект «{project.title}».',
               reverse('project_detail', args=[project.pk]))
        award(self.request.user, 'critic')
        messages.success(self.request, 'Оценка добавлена!')
        return response

    def get_success_url(self):
        return reverse('project_detail', args=[self.object.project.pk])


@login_required
def project_criteria_json(request, pk):
    project = get_object_or_404(Project, pk=pk)
    criteria = list(project.contest.criteria.values('id', 'name', 'max_score'))
    return JsonResponse({'criteria': criteria})


# ------------------------------------------------------------- AJAX-действия
@login_required
@require_POST
@ratelimit(key='user', rate='30/m', block=True)
def vote_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.status == 'draft':
        return JsonResponse({'success': False, 'message': 'Нельзя голосовать за черновик.'}, status=400)
    if project.contest.results_finalized:
        return JsonResponse({'success': False, 'message': 'Итоги подведены — голосование заморожено.'}, status=400)
    if project.is_member(request.user):
        return JsonResponse({'success': False, 'message': 'Нельзя голосовать за проект своей команды.'}, status=400)
    vote, created = ProjectVote.objects.get_or_create(project=project, user=request.user)
    if not created:
        vote.delete()
    else:
        award(request.user, 'voter')
    project.votes = project.project_votes.count()
    project.save(update_fields=['votes'])
    return JsonResponse({'success': True, 'votes': project.votes, 'voted': created})


@login_required
@require_POST
def change_status(request, pk):
    if not is_organizer(request.user):
        return JsonResponse({'success': False, 'message': 'Нет прав'}, status=403)
    project = get_object_or_404(Project, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Project.STATUS_CHOICES):
        set_project_status(project, new_status, request.user)
        return JsonResponse({'success': True, 'status': project.status,
                             'status_display': project.get_status_display()})
    return JsonResponse({'success': False, 'message': 'Неверный статус'}, status=400)


@login_required
@require_POST
@ratelimit(key='user', rate='30/m', block=True)
def add_comment_ajax(request, pk):
    project = get_object_or_404(Project, pk=pk)
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'success': False, 'message': 'Пустой комментарий'}, status=400)
    if len(text) > 2000:
        return JsonResponse({'success': False, 'message': 'Комментарий слишком длинный (макс. 2000 символов).'}, status=400)
    parent = None
    parent_id = request.POST.get('parent_id')
    if parent_id:
        parent = Comment.objects.filter(pk=parent_id, project=project).first()
    comment = Comment.objects.create(project=project, author=request.user, text=text, parent=parent)
    award(request.user, 'talker')
    url = reverse('project_detail', args=[project.pk])
    recipients = set(project.all_members())
    if project.mentor:
        recipients.add(project.mentor)
    if parent:
        recipients.add(parent.author)
    recipients.update(parse_mentions(text))
    notify(recipients, request.user, f'Новый комментарий к проекту «{project.title}».', url)
    return JsonResponse({'success': True, 'comment': {
        'id': comment.id, 'parent_id': parent.id if parent else None,
        'author': comment.author.username, 'text': comment.text,
        'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')}})


@login_required
@require_POST
def assign_mentor(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not is_organizer(request.user):
        messages.error(request, 'Назначать наставника может только организатор или администратор.')
        return redirect('project_detail', pk=pk)
    form = MentorAssignForm(request.POST)
    if form.is_valid():
        project.mentor = form.cleaned_data['mentor']
        project.save(update_fields=['mentor', 'updated_at'])
        if project.mentor:
            notify(project.mentor, request.user, f'Вам назначен подопечный проект «{project.title}».',
                   reverse('project_detail', args=[project.pk]))
            award(project.mentor, 'mentor_start')
            messages.success(request, f'Наставник назначен: {project.mentor.username}.')
        else:
            messages.success(request, 'Наставник снят с проекта.')
    else:
        messages.error(request, 'Выбранный пользователь не является наставником.')
    return redirect('project_detail', pk=pk)


@login_required
@require_POST
def assign_expert(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав.')
        return redirect('project_detail', pk=pk)
    form = ExpertAssignForm(request.POST, project=project)
    if form.is_valid():
        expert = form.cleaned_data['expert']
        ExpertAssignment.objects.get_or_create(project=project, expert=expert,
                                               defaults={'assigned_by': request.user})
        notify(expert, request.user, f'Вам назначен проект для экспертизы «{project.title}».',
               reverse('project_detail', args=[project.pk]))
        messages.success(request, f'Эксперт назначен: {expert.username}.')
    else:
        messages.error(request, 'Некорректный выбор эксперта.')
    return redirect('project_detail', pk=pk)


@login_required
@require_POST
def unassign_expert(request, pk):
    assignment = get_object_or_404(ExpertAssignment, pk=pk)
    project = assignment.project
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав.')
        return redirect('project_detail', pk=project.pk)
    assignment.delete()
    messages.success(request, 'Эксперт снят с проекта.')
    return redirect('project_detail', pk=project.pk)


# -------------------------------------------------------------------- команда
@login_required
@require_POST
def invite_team_member(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.participant != request.user:
        messages.error(request, 'Приглашать соавторов может только автор проекта.')
        return redirect('project_detail', pk=pk)
    form = TeamInviteForm(request.POST, project=project)
    if form.is_valid():
        user = User.objects.get(username=form.cleaned_data['username'])
        TeamInvite.objects.create(project=project, user=user, invited_by=request.user)
        notify(user, request.user, f'Вас пригласили в команду проекта «{project.title}».',
               reverse('my_projects'))
        messages.success(request, f'Приглашение отправлено: {user.username}.')
    else:
        messages.error(request, form.errors.as_text())
    return redirect('project_detail', pk=pk)


@login_required
@require_POST
def respond_team_invite(request, pk):
    invite = get_object_or_404(TeamInvite, pk=pk, user=request.user, status='pending')
    action = request.POST.get('action')
    if action == 'accept':
        invite.status = 'accepted'
        invite.save(update_fields=['status'])
        invite.project.team.add(request.user)
        notify(invite.invited_by, request.user,
               f'{request.user.username} принял приглашение в команду «{invite.project.title}».',
               reverse('project_detail', args=[invite.project.pk]))
        messages.success(request, 'Вы в команде проекта!')
    else:
        invite.status = 'declined'
        invite.save(update_fields=['status'])
        notify(invite.invited_by, request.user,
               f'{request.user.username} отклонил приглашение в команду «{invite.project.title}».',
               reverse('project_detail', args=[invite.project.pk]))
        messages.info(request, 'Приглашение отклонено.')
    return redirect('my_projects')


# --------------------------------------------------------------- уведомления
class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'contests/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related('actor')


@login_required
def notification_go(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return redirect(notif.url or 'home')


@login_required
@require_POST
def notifications_read_all(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect(request.POST.get('next') or 'notifications')


# ---------------------------------------------------- результаты и лидерборд
class ContestResultsView(DetailView):
    model = Contest
    template_name = 'contests/results.html'
    context_object_name = 'contest'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contest = self.object
        snapshot = getattr(contest, 'result_snapshot', None)
        if contest.results_finalized and snapshot:
            context['snapshot'] = snapshot.data
            context['ranked'] = []
            context['top3'] = []
        else:
            projects = list(contest.projects.exclude(status='draft').select_related('participant'))
            projects.sort(key=lambda p: (p.weighted_score_percent(), p.votes), reverse=True)
            context['ranked'] = projects
            context['top3'] = projects[:3]
        context['progress'] = contest.evaluation_progress()
        context['can_finalize'] = is_organizer(self.request.user) and contest.can_finalize
        context['bulk_form'] = BulkActionForm(contest=contest)
        return context


@login_required
@require_POST
def contest_finalize(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if not is_organizer(request.user):
        messages.error(request, 'Подводить итоги может только организатор.')
        return redirect('contest_results', pk=pk)
    if contest.results_finalized:
        messages.info(request, 'Итоги уже подведены.')
        return redirect('contest_results', pk=pk)
    if not contest.can_finalize:
        messages.error(request, 'Нельзя подвести итоги: не все проекты полностью оценены экспертами.')
        return redirect('contest_results', pk=pk)
    contest.results_finalized = True
    contest.finalized_at = timezone.now()
    contest.is_active = False
    contest.save(update_fields=['results_finalized', 'finalized_at', 'is_active'])
    for project in contest.projects.filter(status__in=['selected', 'in_progress']):
        set_project_status(project, 'completed', request.user)
    projects = list(contest.projects.exclude(status='draft'))
    projects.sort(key=lambda p: (p.weighted_score_percent(), p.votes), reverse=True)
    ResultSnapshot.objects.update_or_create(contest=contest, defaults={'data': [
        {'rank': i, 'id': p.pk, 'title': p.title, 'participant': p.participant.username,
         'score_percent': p.weighted_score_percent(), 'votes': p.votes,
         'status': p.get_status_display()} for i, p in enumerate(projects, 1)]})
    if projects:
        winner = projects[0]
        for member in winner.all_members():
            award(member, 'winner')
    participants = {p.participant for p in contest.projects.all()}
    notify(participants, request.user, f'Подведены итоги конкурса «{contest.name}»!',
           reverse('contest_results', args=[contest.pk]))
    messages.success(request, 'Итоги конкурса подведены!')
    return redirect('contest_results', pk=pk)


@login_required
def contest_results_pdf(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.results_finalized and not is_organizer(request.user):
        messages.error(request, 'Протокол доступен после подведения итогов.')
        return redirect('contest_results', pk=pk)
    return generate_results_pdf(contest)


class RatingView(TemplateView):
    template_name = 'contests/rating.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cached = cache.get('rating_rows')
        if cached is not None:
            context['rows'] = cached
            return context
        users = (User.objects.annotate(proj_count=Count('projects', distinct=True),
                                       votes_sum=Sum('projects__votes'),
                                       ach_count=Count('achievements', distinct=True))
                 .filter(proj_count__gt=0))
        rows = []
        for user in users:
            projects = Project.objects.filter(participant=user)
            avg_percent = round(sum(p.score_percent() for p in projects) / len(projects), 1) if projects else 0
            points = user.proj_count * 2 + (user.votes_sum or 0) + round(avg_percent / 10) + user.ach_count * 3
            rows.append({'user': user, 'projects': user.proj_count, 'votes': user.votes_sum or 0,
                         'avg_percent': avg_percent, 'achievements': user.ach_count, 'points': points})
        rows.sort(key=lambda r: r['points'], reverse=True)
        cache.set('rating_rows', rows, 60)
        context['rows'] = rows
        return context


# ------------------------------------------------------ личные разделы и профиль
@login_required
def my_projects_view(request):
    projects = (Project.objects.filter(Q(participant=request.user) | Q(team=request.user))
              .select_related('contest', 'mentor').distinct())
    invites = TeamInvite.objects.filter(user=request.user, status='pending').select_related('project', 'invited_by')
    return render(request, 'contests/my_projects.html', {'projects': projects, 'invites': invites})


@login_required
def my_evaluations_view(request):
    evaluations = Evaluation.objects.filter(expert=request.user).select_related('project', 'criterion')
    return render(request, 'contests/my_evaluations.html', {'evaluations': evaluations})


@login_required
def my_mentored_view(request):
    projects = Project.objects.filter(mentor=request.user).select_related('contest', 'participant')
    return render(request, 'contests/my_mentored.html', {'projects': projects})


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'contests/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = primary_role(user)
        context['role_info'] = ROLE_INFO.get(role)
        context['my_projects'] = Project.objects.filter(participant=user).select_related('contest')[:5]
        context['my_evaluations'] = Evaluation.objects.filter(expert=user).select_related('project')[:5]
        context['my_mentored'] = Project.objects.filter(mentor=user).select_related('contest')[:5]
        earned = {ua.achievement_id for ua in user.achievements.all()}
        context['achievements'] = [{'achievement': a, 'earned': a.id in earned}
                                   for a in Achievement.objects.all()]
        context['stats'] = {
            'projects': Project.objects.filter(participant=user).count(),
            'evaluations': Evaluation.objects.filter(expert=user).count(),
            'comments': Comment.objects.filter(author=user).count(),
            'mentored': Project.objects.filter(mentor=user).count(),
            'votes_given': ProjectVote.objects.filter(user=user).count(),
        }
        return context


# ------------------------------------------------------- дашборд и роли (админ)
class DashboardView(LoginRequiredMixin, OrganizerRequiredMixin, TemplateView):
    template_name = 'contests/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stats = cache.get('dashboard_stats')
        if stats is None:
            statuses = Project.objects.values('status').annotate(count=Count('id'))
            contests = Contest.objects.annotate(project_count=Count('projects')).order_by('-project_count')[:5]
            stats = {
                'status_labels': [dict(Project.STATUS_CHOICES).get(s['status'], s['status']) for s in statuses],
                'status_data': [s['count'] for s in statuses],
                'contest_labels': [c.name for c in contests],
                'contest_data': [c.project_count for c in contests],
                'counts': {'contests': Contest.objects.count(), 'projects': Project.objects.count(),
                           'users': User.objects.count(), 'evaluations': Evaluation.objects.count()},
            }
            cache.set('dashboard_stats', stats, 60)
        context['status_labels'] = stats['status_labels']
        context['status_data'] = stats['status_data']
        context['contest_labels'] = stats['contest_labels']
        context['contest_data'] = stats['contest_data']
        context['stats'] = stats['counts']
        context['role_counts'] = [
            {'label': ROLE_INFO[r]['label'], 'css': ROLE_INFO[r]['css'], 'icon': ROLE_INFO[r]['icon'],
             'count': User.objects.filter(groups__name=r).count()} for r in ALL_ROLES]
        context['recent_projects'] = Project.objects.select_related('contest', 'participant')[:6]
        context['import_form'] = ImportCSVForm()
        return context


class RoleManagementView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = 'contests/role_management.html'
    context_object_name = 'managed_users'
    paginate_by = 15

    def get_queryset(self):
        queryset = User.objects.prefetch_related('groups').order_by('username')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(username__icontains=query) | Q(first_name__icontains=query)
                                       | Q(last_name__icontains=query) | Q(email__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for user in context['managed_users']:
            role = primary_role(user)
            user.role_key = role
            user.role_info = ROLE_INFO.get(role)
            user.role_form = RoleAssignForm(initial={'user_id': user.pk, 'role': role})
        context['q'] = self.request.GET.get('q', '')
        context['roles'] = [(r, ROLE_INFO[r]) for r in ALL_ROLES]
        return context

    def post(self, request, *args, **kwargs):
        form = RoleAssignForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Некорректные данные формы.')
            return redirect('role_management')
        target = get_object_or_404(User, pk=form.cleaned_data['user_id'])
        role = form.cleaned_data['role']
        if target.pk == request.user.pk:
            messages.error(request, 'Нельзя изменить собственную роль — попросите другого администратора.')
        elif target.is_superuser:
            messages.error(request, 'Роль суперпользователя меняется только в админ-панели Django.')
        else:
            set_role(target, role)
            notify(target, request.user, f'Вам назначена роль «{ROLE_INFO[role]["label"]}».', reverse('profile'))
            messages.success(request, f'Пользователю {target.username} назначена роль «{ROLE_INFO[role]["label"]}».')
        return redirect('role_management')


# ------------------------------------------------------------- экспорт / импорт
@login_required
def export_projects_view(request):
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав')
        return redirect('home')
    return export_projects_csv(Project.objects.select_related('contest', 'participant', 'mentor'))


@login_required
def export_evaluations_view(request):
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав')
        return redirect('home')
    return export_evaluations_csv(Evaluation.objects.select_related('project', 'expert', 'criterion'))
