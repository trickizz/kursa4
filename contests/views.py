from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.generic import (ListView, DetailView, CreateView,
                                  UpdateView, DeleteView, TemplateView, FormView)
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST

from .models import (Contest, Project, Evaluation, Comment, Criterion,
                     Stage, Document, ProjectVote)
from .forms import (ContestForm, ProjectForm, ProjectSubmitForm, CommentForm,
                    DocumentForm, RegisterForm, EvaluationForm, StageForm,
                    CriterionForm, MentorAssignForm, RoleAssignForm, ImportCSVForm)
from .mixins import (OrganizerRequiredMixin, ExpertRequiredMixin,
                     ParticipantRequiredMixin, AdminRequiredMixin)
from .roles import (has_role, is_site_admin, is_organizer, is_expert,
                    primary_role, set_role, ROLE_INFO, ALL_ROLES, ROLE_ADMIN)
from .utils import export_projects_csv, export_evaluations_csv


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
                .annotate(project_count=Count('projects'))
                .order_by('-created_at')[:6])

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
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(description__icontains=query))
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
        context['projects'] = (self.object.projects.exclude(status='draft')
                               .select_related('participant', 'mentor'))
        context['stage_form'] = StageForm()
        context['criterion_form'] = CriterionForm()
        return context


class ProjectListView(ListView):
    model = Project
    template_name = 'contests/project_list.html'
    context_object_name = 'projects'
    paginate_by = 9

    def get_queryset(self):
        queryset = (Project.objects.exclude(status='draft')
                    .select_related('contest', 'participant')
                    .order_by('-created_at'))
        contest_id = self.request.GET.get('contest')
        status = self.request.GET.get('status')
        query = self.request.GET.get('q', '').strip()
        if contest_id:
            queryset = queryset.filter(contest_id=contest_id)
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(summary__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contests'] = Contest.objects.all()
        context['status_choices'] = Project.STATUS_CHOICES
        context['current_contest'] = self.request.GET.get('contest', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['q'] = self.request.GET.get('q', '')
        return context


class ProjectDetailView(DetailView):
    model = Project
    template_name = 'contests/project_detail.html'
    context_object_name = 'project'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        # Черновик виден только автору, организаторам и админам
        if obj.status == 'draft' and obj.participant != user and not is_organizer(user):
            raise Http404('Черновик недоступен')
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj, user = self.object, self.request.user
        can_manage = is_organizer(user)
        is_owner = user.is_authenticated and obj.participant_id == user.pk

        context['evaluations'] = obj.evaluations.select_related('expert', 'criterion')
        context['comments'] = obj.comments.select_related('author')
        context['documents'] = obj.documents.all()
        context['document_form'] = DocumentForm()
        context['mentor_form'] = MentorAssignForm(initial={'mentor': obj.mentor})
        context['status_choices'] = Project.STATUS_CHOICES
        context['user_voted'] = (user.is_authenticated and
                                 ProjectVote.objects.filter(project=obj, user=user).exists())
        context['is_owner'] = is_owner
        context['can_edit'] = (is_owner and obj.is_editable_by_participant()) or can_manage
        context['can_submit'] = is_owner and obj.is_editable_by_participant()
        context['can_delete'] = is_owner or can_manage
        context['can_upload'] = is_owner or can_manage or (
            user.is_authenticated and obj.mentor_id == user.pk)
        context['can_evaluate'] = (is_expert(user) and not is_owner
                                   and obj.status != 'draft')
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
        messages.success(self.request, 'Проект создан как черновик. Загрузите документы и отправьте его на конкурс!')
        return super().form_valid(form)


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'contests/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        owner_ok = (obj.participant == request.user
                    and obj.is_editable_by_participant())
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
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.status = 'submitted'
        messages.success(self.request, 'Проект отправлен на конкурс!')
        return super().form_valid(form)


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
        allowed = (self.project.participant == user or is_organizer(user)
                   or self.project.mentor_id == user.pk)
        if request.user.is_authenticated and not allowed:
            messages.error(request, 'Загружать документы могут автор, наставник проекта или организатор.')
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
        messages.success(self.request, 'Оценка добавлена!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('project_detail', args=[self.object.project.pk])


@login_required
def project_criteria_json(request, pk):
    """Критерии конкурса проекта — для динамической формы оценки."""
    project = get_object_or_404(Project, pk=pk)
    criteria = list(project.contest.criteria.values('id', 'name', 'max_score'))
    return JsonResponse({'criteria': criteria})


# ------------------------------------------------------------- AJAX-действия

@login_required
@require_POST
def vote_project(request, pk):
    """Один пользователь — один голос. Повторный клик снимает голос."""
    project = get_object_or_404(Project, pk=pk)
    if project.status == 'draft':
        return JsonResponse({'success': False, 'message': 'Нельзя голосовать за черновик.'}, status=400)
    if project.participant_id == request.user.pk:
        return JsonResponse({'success': False, 'message': 'Нельзя голосовать за свой проект.'}, status=400)

    vote, created = ProjectVote.objects.get_or_create(project=project, user=request.user)
    if not created:
        vote.delete()
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
        project.status = new_status
        project.save(update_fields=['status', 'updated_at'])
        return JsonResponse({'success': True,
                             'status': project.status,
                             'status_display': project.get_status_display()})
    return JsonResponse({'success': False, 'message': 'Неверный статус'}, status=400)


@login_required
@require_POST
def add_comment_ajax(request, pk):
    project = get_object_or_404(Project, pk=pk)
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'success': False, 'message': 'Пустой комментарий'}, status=400)
    if len(text) > 2000:
        return JsonResponse({'success': False, 'message': 'Комментарий слишком длинный (макс. 2000 символов).'}, status=400)

    comment = Comment.objects.create(project=project, author=request.user, text=text)
    return JsonResponse({'success': True,
                         'comment': {
                             'author': comment.author.username,
                             'text': comment.text,
                             'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
                         }})


@login_required
@require_POST
def assign_mentor(request, pk):
    """Организатор/админ назначает проекту наставника из группы Mentor."""
    project = get_object_or_404(Project, pk=pk)
    if not is_organizer(request.user):
        messages.error(request, 'Назначать наставника может только организатор или администратор.')
        return redirect('project_detail', pk=pk)
    form = MentorAssignForm(request.POST)
    if form.is_valid():
        project.mentor = form.cleaned_data['mentor']
        project.save(update_fields=['mentor', 'updated_at'])
        if project.mentor:
            messages.success(request, f'Наставник назначен: {project.mentor.username}.')
        else:
            messages.success(request, 'Наставник снят с проекта.')
    else:
        messages.error(request, 'Выбранный пользователь не является наставником.')
    return redirect('project_detail', pk=pk)


# ------------------------------------------------------ личные разделы и профиль

@login_required
def my_projects_view(request):
    projects = (Project.objects.filter(participant=request.user)
                .select_related('contest', 'mentor'))
    return render(request, 'contests/my_projects.html', {'projects': projects})


@login_required
def my_evaluations_view(request):
    evaluations = (Evaluation.objects.filter(expert=request.user)
                   .select_related('project', 'criterion'))
    return render(request, 'contests/my_evaluations.html', {'evaluations': evaluations})


@login_required
def my_mentored_view(request):
    projects = (Project.objects.filter(mentor=request.user)
                .select_related('contest', 'participant'))
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
        statuses = Project.objects.values('status').annotate(count=Count('id'))
        context['status_labels'] = [dict(Project.STATUS_CHOICES).get(s['status'], s['status']) for s in statuses]
        context['status_data'] = [s['count'] for s in statuses]

        contests = Contest.objects.annotate(project_count=Count('projects')).order_by('-project_count')[:5]
        context['contest_labels'] = [c.name for c in contests]
        context['contest_data'] = [c.project_count for c in contests]

        context['stats'] = {
            'contests': Contest.objects.count(),
            'projects': Project.objects.count(),
            'users': User.objects.count(),
            'evaluations': Evaluation.objects.count(),
        }
        context['role_counts'] = [
            {'label': ROLE_INFO[role]['label'], 'css': ROLE_INFO[role]['css'],
             'icon': ROLE_INFO[role]['icon'],
             'count': User.objects.filter(groups__name=role).count()}
            for role in ALL_ROLES
        ]
        context['recent_projects'] = Project.objects.select_related('contest', 'participant')[:6]
        context['import_form'] = ImportCSVForm()
        return context


class RoleManagementView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Администратор назначает роли — роль сразу меняет меню и права."""
    model = User
    template_name = 'contests/role_management.html'
    context_object_name = 'managed_users'
    paginate_by = 15

    def get_queryset(self):
        queryset = User.objects.prefetch_related('groups').order_by('username')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) | Q(first_name__icontains=query)
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
        context['roles'] = [(role, ROLE_INFO[role]) for role in ALL_ROLES]
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
