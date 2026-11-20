from django import forms
from django.contrib.auth.models import User, Group
from .models import Contest, Project, Comment, Document


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


class RegisterForm(forms.ModelForm):
    ROLE_CHOICES = [
        ('Participant', 'Участник — хочу подать проект на конкурс'),
        ('Mentor', 'Наставник — хочу помогать участникам'),
        ('Expert', 'Эксперт — хочу оценивать проекты'),
    ]

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
        choices=ROLE_CHOICES,
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

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким логином уже существует.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Пароли не совпадают.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            role_name = self.cleaned_data['role']
            group, _ = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)
        return user