from django import forms
from django.contrib.auth.models import User, Group
from django.db.models import Q

from .models import Contest, Project, Comment, Document, Evaluation, Criterion, Stage
from .roles import ROLE_INFO, SELF_SIGNUP_ROLES, ALL_ROLES, ROLE_MENTOR, set_role


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = ['name', 'description', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control',
                                           'placeholder': 'Например: Конкурс проектов 2026'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5,
                                                 'placeholder': 'Кратко опишите конкурс'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                                 'placeholder': 'Что нужно сделать на этом этапе'}),
        }


class CriterionForm(forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ['name', 'max_score']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Новизна идеи'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'summary', 'contest']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'Название проекта'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 5,
                                             'placeholder': 'Краткое описание'}),
            'contest': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Contest.objects.filter(is_active=True)
        if self.instance.pk:
            queryset = Contest.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.contest_id))
        self.fields['contest'].queryset = queryset


class ProjectSubmitForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = []


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                          'placeholder': 'Ваш комментарий...'}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['file', 'description']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control',
                                                  'placeholder': 'Описание файла'}),
        }


class EvaluationForm(forms.ModelForm):
    """Оценка эксперта: критерий должен относиться к конкурсу проекта,
    балл не выше максимума, без дублей и без оценки собственного проекта."""
    class Meta:
        model = Evaluation
        fields = ['project', 'criterion', 'score', 'comment']
        labels = {'score': 'Балл', 'comment': 'Комментарий эксперта'}
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'criterion': forms.Select(attrs={'class': 'form-select'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                             'placeholder': 'Обоснование оценки (необязательно)'}),
        }

    def __init__(self, *args, expert=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.expert = expert
        projects = Project.objects.exclude(status='draft').select_related('contest')
        if expert is not None:
            projects = projects.exclude(participant=expert)
        self.fields['project'].queryset = projects
        self.fields['criterion'].queryset = Criterion.objects.select_related('contest')

        project_id = self.data.get('project') or self.initial.get('project')
        if project_id:
            try:
                project = Project.objects.get(pk=project_id)
                self.fields['criterion'].queryset = Criterion.objects.filter(
                    contest=project.contest)
            except (Project.DoesNotExist, ValueError, TypeError):
                pass

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get('project')
        criterion = cleaned.get('criterion')
        score = cleaned.get('score')

        if project and criterion and criterion.contest_id != project.contest_id:
            raise forms.ValidationError(
                'Критерий не относится к конкурсу выбранного проекта.')
        if criterion and score is not None and score > criterion.max_score:
            raise forms.ValidationError(
                f'Балл не может превышать {criterion.max_score} '
                f'по критерию «{criterion.name}».')
        if project and self.expert and project.participant_id == self.expert.pk:
            raise forms.ValidationError('Нельзя оценивать собственный проект.')
        if project and criterion and self.expert:
            duplicates = Evaluation.objects.filter(
                project=project, criterion=criterion, expert=self.expert)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise forms.ValidationError(
                    'Вы уже оценили этот проект по выбранному критерию.')
        return cleaned


class MentorAssignForm(forms.Form):
    """Назначение наставника проекту (организатор/админ)."""
    mentor = forms.ModelChoiceField(
        label='Наставник',
        queryset=User.objects.filter(groups__name=ROLE_MENTOR).order_by('username'),
        required=False,
        empty_label='— Без наставника —',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class RoleAssignForm(forms.Form):
    """Смена роли пользователя администратором."""
    user_id = forms.IntegerField(widget=forms.HiddenInput)
    role = forms.ChoiceField(
        choices=[(role, ROLE_INFO[role]['label']) for role in ALL_ROLES],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )


class ImportCSVForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV-файл',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv'}),
        help_text='Колонки: Название; Конкурс; Участник; Описание; Статус (разделитель «;»)',
    )


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control',
                                          'placeholder': 'Минимум 8 символов'}),
        min_length=8,
    )
    password2 = forms.CharField(
        label='Повторите пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control',
                                          'placeholder': 'Введите пароль ещё раз'}),
    )
    role = forms.ChoiceField(
        label='Роль в системе',
        choices=[(role, f"{ROLE_INFO[role]['label']} — {ROLE_INFO[role]['description']}")
                 for role in SELF_SIGNUP_ROLES],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control',
                                               'placeholder': 'Логин (латиница, без пробелов)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control',
                                             'placeholder': 'you@example.com'}),
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
