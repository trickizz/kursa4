from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .models import (Contest, Project, Comment, Document, Evaluation, Criterion,
                     Stage, TeamInvite, Tag, Appeal, MentorTask)
from .roles import ROLE_INFO, SELF_SIGNUP_ROLES, ALL_ROLES, ROLE_MENTOR, ROLE_EXPERT, set_role


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = ['name', 'description', 'start_date', 'end_date', 'is_active', 'cover']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Конкурс проектов 2026'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Кратко опишите конкурс'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cover': forms.ClearableFileInput(attrs={'class': 'form-control dropzone', 'accept': 'image/*'}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('Дата окончания не может быть раньше даты начала.')
        return cleaned


class StageForm(forms.ModelForm):
    class Meta:
        model = Stage
        fields = ['name', 'order', 'deadline', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название этапа'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Что нужно сделать на этом этапе'}),
        }


class CriterionForm(forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ['name', 'max_score', 'weight']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Новизна идеи'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['weight'].required = False
        self.fields['weight'].initial = 1

    def clean_weight(self):
        return self.cleaned_data.get('weight') or 1


class ProjectForm(forms.ModelForm):
    tags = forms.CharField(label='Теги', required=False,
                           widget=forms.TextInput(attrs={'class': 'form-control',
                                                         'placeholder': 'через запятую: веб, ИИ, экология'}))

    class Meta:
        model = Project
        fields = ['title', 'summary', 'contest', 'cover', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название проекта'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Краткое описание'}),
            'contest': forms.Select(attrs={'class': 'form-select'}),
            'cover': forms.ClearableFileInput(attrs={'class': 'form-control dropzone', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        open_contests = Contest.objects.filter(is_active=True, results_finalized=False,
                                               end_date__gte=timezone.localdate())
        if self.instance.pk:
            queryset = Contest.objects.filter(Q(pk__in=open_contests) | Q(pk=self.instance.contest_id))
        else:
            queryset = open_contests
        self.fields['contest'].queryset = queryset
        if self.instance.pk:
            self.fields['tags'].initial = ', '.join(t.name for t in self.instance.tags.all())

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            names = [t.strip() for t in self.cleaned_data.get('tags', '').split(',') if t.strip()][:10]
            tag_objs = [Tag.objects.get_or_create(name=n)[0] for n in names]
            instance.tags.set(tag_objs)
        return instance


class ProjectSubmitForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = []


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ваш комментарий...'})}


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['file', 'description']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control dropzone'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Описание файла'}),
        }


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ['project', 'criterion', 'score', 'comment']
        labels = {'score': 'Балл', 'comment': 'Комментарий эксперта'}
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'criterion': forms.Select(attrs={'class': 'form-select'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Обоснование оценки (необязательно)'}),
        }

    def __init__(self, *args, expert=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.expert = expert
        projects = Project.objects.exclude(status='draft').select_related('contest')
        if expert is not None:
            projects = projects.exclude(participant=expert).exclude(team=expert)
        self.fields['project'].queryset = projects
        self.fields['criterion'].queryset = Criterion.objects.select_related('contest')
        project_id = self.data.get('project') or self.initial.get('project')
        if project_id:
            try:
                project = Project.objects.get(pk=project_id)
                self.fields['criterion'].queryset = Criterion.objects.filter(contest=project.contest)
            except (Project.DoesNotExist, ValueError, TypeError):
                pass

    def clean(self):
        cleaned = super().clean()
        project, criterion, score = cleaned.get('project'), cleaned.get('criterion'), cleaned.get('score')
        if project and criterion and criterion.contest_id != project.contest_id:
            raise forms.ValidationError('Критерий не относится к конкурсу выбранного проекта.')
        if criterion and score is not None and score > criterion.max_score:
            raise forms.ValidationError(f'Балл не может превышать {criterion.max_score} по критерию «{criterion.name}».')
        if project and project.contest.results_finalized:
            raise forms.ValidationError('Итоги конкурса подведены — оценки заморожены.')
        if project and self.expert:
            if project.participant_id == self.expert.pk or project.team.filter(pk=self.expert.pk).exists():
                raise forms.ValidationError('Нельзя оценивать проект своей команды.')
            assignments = project.expert_assignments.all()
            if assignments.exists() and not assignments.filter(expert=self.expert).exists():
                raise forms.ValidationError('Этот проект закреплён за другими экспертами.')
            duplicates = Evaluation.objects.filter(project=project, criterion=criterion, expert=self.expert)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if criterion and duplicates.exists():
                raise forms.ValidationError('Вы уже оценили этот проект по выбранному критерию.')
        return cleaned


class MentorAssignForm(forms.Form):
    mentor = forms.ModelChoiceField(
        label='Наставник',
        queryset=User.objects.filter(groups__name=ROLE_MENTOR).order_by('username'),
        required=False, empty_label='— Без наставника —',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class ExpertAssignForm(forms.Form):
    expert = forms.ModelChoiceField(
        label='Эксперт', queryset=User.objects.filter(groups__name=ROLE_EXPERT),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            member_ids = [project.participant_id] + list(project.team.values_list('pk', flat=True))
            self.fields['expert'].queryset = (
                User.objects.filter(groups__name=ROLE_EXPERT)
                .exclude(pk__in=member_ids)
                .exclude(expert_assignments__project=project)
                .order_by('username'))


class TeamInviteForm(forms.Form):
    username = forms.CharField(label='Логин соавтора', max_length=150,
                               widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'username'}))

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError('Пользователь с таким логином не найден.')
        if self.project:
            if user.pk == self.project.participant_id or self.project.team.filter(pk=user.pk).exists():
                raise forms.ValidationError('Этот пользователь уже в команде.')
            if TeamInvite.objects.filter(project=self.project, user=user, status='pending').exists():
                raise forms.ValidationError('Приглашение уже отправлено.')
        return username


class RoleAssignForm(forms.Form):
    user_id = forms.IntegerField(widget=forms.HiddenInput)
    role = forms.ChoiceField(choices=[(r, ROLE_INFO[r]['label']) for r in ALL_ROLES],
                             widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))


class ImportCSVForm(forms.Form):
    csv_file = forms.FileField(label='CSV-файл',
                               widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv'}),
                               help_text='Колонки: Название; Конкурс; Участник; Описание; Статус (разделитель «;»)')


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label='Пароль', min_length=8,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Минимум 8 символов'}))
    password2 = forms.CharField(label='Повторите пароль',
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Введите пароль ещё раз'}))
    role = forms.ChoiceField(label='Роль в системе',
                             choices=[(r, f"{ROLE_INFO[r]['label']} — {ROLE_INFO[r]['description']}") for r in SELF_SIGNUP_ROLES],
                             widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Логин (латиница, без пробелов)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким логином уже существует.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Пароли не совпадают.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            set_role(user, self.cleaned_data['role'])
        return user


class AppealForm(forms.ModelForm):
    class Meta:
        model = Appeal
        fields = ['reason']
        widgets = {'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                   'placeholder': 'Почему вы не согласны с оценкой?'})}


class AppealResolveForm(forms.Form):
    status = forms.ChoiceField(label='Решение', choices=[('accepted', 'Удовлетворить'), ('rejected', 'Отклонить')],
                               widget=forms.Select(attrs={'class': 'form-select'}))
    resolution = forms.CharField(label='Комментарий', required=False,
                                 widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class MentorTaskForm(forms.ModelForm):
    class Meta:
        model = MentorTask
        fields = ['text']
        widgets = {'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Новая задача для участника'})}


class BulkActionForm(forms.Form):
    project_ids = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=True)
    action = forms.ChoiceField(choices=[('status', 'Сменить статус'), ('expert', 'Назначить эксперта')],
                               widget=forms.Select(attrs={'class': 'form-select'}))
    status = forms.ChoiceField(choices=Project.STATUS_CHOICES, required=False,
                               widget=forms.Select(attrs={'class': 'form-select'}))
    expert = forms.ModelChoiceField(queryset=User.objects.filter(groups__name=ROLE_EXPERT), required=False,
                                    widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, contest=None, **kwargs):
        super().__init__(*args, **kwargs)
        if contest is not None:
            self.fields['project_ids'].choices = [
                (p.pk, p.title) for p in contest.projects.exclude(status='draft')]
