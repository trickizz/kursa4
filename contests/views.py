from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import (ListView, DetailView, CreateView,
                                  UpdateView, DeleteView, TemplateView, FormView)
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Contest, Project, Evaluation, Comment
from .forms import (ContestForm, ProjectForm, ProjectSubmitForm,
                    CommentForm, DocumentForm, RegisterForm)
from .mixins import OrganizerRequiredMixin, ExpertRequiredMixin, ParticipantRequiredMixin
from .utils import export_projects_csv, export_evaluations_csv, import_projects_csv


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


class HomeView(ListView):
    model = Contest
    template_name = 'contests/home.html'
    context_object_name = 'contests'

    def get_queryset(self):
        return Contest.objects.filter(is_active=True).order_by('-created_at')[:6]


class ContestListView(ListView):
    model = Contest
    template_name = 'contests/contest_list.html'
    context_object_name = 'contests'
    paginate_by = 10


class ContestDetailView(DetailView):
    model = Contest
    template_name = 'contests/contest_detail.html'
    context_object_name = 'contest'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stages'] = self.object.stages.all().order_by('order')
        context['criteria'] = self.object.criteria.all()
        return context


class ContestCreateView(LoginRequiredMixin, OrganizerRequiredMixin, CreateView):
    model = Contest
    form_class = ContestForm
    template_name = 'contests/contest_form.html'
    success_url = reverse_lazy('contest_list')

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        return super().form_valid(form)


class ContestUpdateView(LoginRequiredMixin, OrganizerRequiredMixin, UpdateView):
    model = Contest
    form_class = ContestForm
    template_name = 'contests/contest_form.html'


class ContestDeleteView(LoginRequiredMixin, OrganizerRequiredMixin, DeleteView):
    model = Contest
    template_name = 'contests/contest_confirm_delete.html'
    success_url = reverse_lazy('contest_list')


class ProjectListView(ListView):
    model = Project
    template_name = 'contests/project_list.html'
    context_object_name = 'projects'
    paginate_by = 10

    def get_queryset(self):
        queryset = Project.objects.exclude(status='draft')
        contest_id = self.request.GET.get('contest')
        status = self.request.GET.get('status')
        if contest_id:
            queryset = queryset.filter(contest_id=contest_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class ProjectDetailView(DetailView):
    model = Project
    template_name = 'contests/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evaluations'] = self.object.evaluations.all()
        context['comments'] = self.object.comments.all()
        context['documents'] = self.object.documents.all()
        context['comment_form'] = CommentForm()
        context['document_form'] = DocumentForm()
        return context


class ProjectCreateView(LoginRequiredMixin, ParticipantRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'contests/project_form.html'

    def form_valid(self, form):
        form.instance.participant = self.request.user
        messages.success(self.request, 'Проект создан!')
        return super().form_valid(form)


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'contests/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.participant != request.user and not request.user.is_superuser:
            messages.error(request, 'Вы не можете редактировать этот проект')
            return redirect('project_list')
        return super().dispatch(request, *args, **kwargs)


class ProjectSubmitView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectSubmitForm
    template_name = 'contests/project_submit.html'

    def form_valid(self, form):
        form.instance.status = 'submitted'
        messages.success(self.request, 'Проект отправлен!')
        return super().form_valid(form)


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Project
    template_name = 'contests/project_confirm_delete.html'
    success_url = reverse_lazy('project_list')


class EvaluationCreateView(LoginRequiredMixin, ExpertRequiredMixin, CreateView):
    model = Evaluation
    fields = ['project', 'criterion', 'score', 'comment']
    template_name = 'contests/evaluation_form.html'

    def form_valid(self, form):
        form.instance.expert = self.request.user
        messages.success(self.request, 'Оценка добавлена!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('project_detail', args=[self.object.project.pk])


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'contests/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if not (user.is_superuser or
                user.groups.filter(name__in=['Organizer', 'Admin']).exists()):
            context['no_access'] = True
            return context

        statuses = Project.objects.values('status').annotate(count=Count('id'))
        context['status_labels'] = [dict(Project.STATUS_CHOICES).get(s['status'], s['status']) for s in statuses]
        context['status_data'] = [s['count'] for s in statuses]

        contests = Contest.objects.annotate(project_count=Count('projects')).order_by('-project_count')[:5]
        context['contest_labels'] = [c.name for c in contests]
        context['contest_data'] = [c.project_count for c in contests]

        return context


@login_required
def my_projects_view(request):
    projects = Project.objects.filter(participant=request.user)
    return render(request, 'contests/my_projects.html', {'projects': projects})


@login_required
def my_evaluations_view(request):
    evaluations = Evaluation.objects.filter(expert=request.user)
    return render(request, 'contests/my_evaluations.html', {'evaluations': evaluations})


@login_required
def export_projects_view(request):
    if not (request.user.is_superuser or
            request.user.groups.filter(name__in=['Organizer', 'Admin']).exists()):
        messages.error(request, 'Нет прав')
        return redirect('home')
    return export_projects_csv(Project.objects.all())


@login_required
def export_evaluations_view(request):
    if not (request.user.is_superuser or
            request.user.groups.filter(name__in=['Organizer', 'Admin']).exists()):
        messages.error(request, 'Нет прав')
        return redirect('home')
    return export_evaluations_csv(Evaluation.objects.all())


@login_required
@require_POST
def vote_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.votes += 1
    project.save()
    return JsonResponse({'success': True, 'votes': project.votes})


@login_required
@require_POST
def change_status(request, pk):
    if not (request.user.is_superuser or
            request.user.groups.filter(name='Organizer').exists()):
        return JsonResponse({'success': False, 'message': 'Нет прав'}, status=403)

    project = get_object_or_404(Project, pk=pk)
    new_status = request.POST.get('status')

    if new_status in dict(Project.STATUS_CHOICES):
        project.status = new_status
        project.save()
        return JsonResponse({'success': True,
                             'status_display': project.get_status_display()})
    return JsonResponse({'success': False, 'message': 'Неверный статус'}, status=400)


@login_required
@require_POST
def add_comment_ajax(request, pk):
    project = get_object_or_404(Project, pk=pk)
    text = request.POST.get('text', '').strip()

    if not text:
        return JsonResponse({'success': False, 'message': 'Пустой комментарий'}, status=400)

    comment = Comment.objects.create(project=project, author=request.user, text=text)
    return JsonResponse({'success': True,
                         'comment': {
                             'author': comment.author.username,
                             'text': comment.text,
                             'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
                         }})