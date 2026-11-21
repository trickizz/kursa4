from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError


class Contest(models.Model):
    name = models.CharField('Название', max_length=200)
    description = models.TextField('Описание')
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания')
    is_active = models.BooleanField('Активен', default=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='organized_contests',
                                  verbose_name='Организатор')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Конкурс'
        verbose_name_plural = 'Конкурсы'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('contest_detail', args=[self.pk])

    @property
    def is_open(self):
        return self.is_active and not self.results_finalized and self.end_date >= timezone.localdate()

    @property
    def days_left(self):
        return (self.end_date - timezone.localdate()).days


def _limit_size(file, mb):
    if file.size > mb * 1024 * 1024:
        raise ValidationError(f'Файл слишком большой (максимум {mb} МБ).')


def validate_cover_size(file):
    _limit_size(file, 5)


def validate_document_size(file):
    _limit_size(file, 10)


class Stage(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE,
                                related_name='stages', verbose_name='Конкурс')
    name = models.CharField('Название этапа', max_length=100)
    order = models.PositiveIntegerField('Порядок')
    deadline = models.DateField('Дедлайн')
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Этап'
        verbose_name_plural = 'Этапы'
        ordering = ['order']

    def __str__(self):
        return f'{self.contest.name} — {self.name}'


class Project(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('submitted', 'Подана'),
        ('under_review', 'На рассмотрении'),
        ('selected', 'Отобран'),
        ('in_progress', 'В работе'),
        ('completed', 'Завершён'),
        ('rejected', 'Отклонён'),
    ]

    title = models.CharField('Название проекта', max_length=200)
    summary = models.TextField('Краткое описание')
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE,
                                related_name='projects', verbose_name='Конкурс')
    participant = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='projects', verbose_name='Участник')
    mentor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='mentored_projects',
                               verbose_name='Наставник')
    status = models.CharField('Статус', max_length=20,
                              choices=STATUS_CHOICES, default='draft')
    votes = models.PositiveIntegerField('Голоса', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['contest', 'status']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('project_detail', args=[self.pk])

    def average_score(self):
        evaluations = self.evaluations.all()
        if evaluations:
            return round(sum(e.score for e in evaluations) / evaluations.count(), 2)
        return 0

    def evaluations_count(self):
        return self.evaluations.count()

    def score_percent(self):
        evaluations = self.evaluations.select_related('criterion')
        if not evaluations:
            return 0
        total = sum(e.score / e.criterion.max_score * 100 for e in evaluations if e.criterion.max_score)
        return round(total / len(evaluations), 1)

    def all_members(self):
        return [self.participant] + list(self.team.all())

    def is_member(self, user):
        return user.is_authenticated and (self.participant_id == user.pk or self.team.filter(pk=user.pk).exists())

    def is_editable_by_participant(self):
        """Участник может редактировать/подавать только черновик или отклонённый проект."""
        return self.status in ('draft', 'rejected')


class Criterion(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE,
                                related_name='criteria', verbose_name='Конкурс')
    name = models.CharField('Название критерия', max_length=100)
    max_score = models.PositiveIntegerField('Максимальный балл')

    class Meta:
        verbose_name = 'Критерий'
        verbose_name_plural = 'Критерии'

    def __str__(self):
        return f'{self.contest.name} — {self.name} ({self.max_score})'


class Evaluation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='evaluations', verbose_name='Проект')
    expert = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='evaluations', verbose_name='Эксперт')
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE,
                                  verbose_name='Критерий')
    score = models.PositiveIntegerField('Оценка')
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Оценка'
        verbose_name_plural = 'Оценки'
        unique_together = ['project', 'expert', 'criterion']

    def __str__(self):
        return f'{self.project.title} — {self.criterion.name}: {self.score}'


class Comment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='comments', verbose_name='Проект')
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               verbose_name='Автор')
    text = models.TextField('Текст')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author.username} — {self.project.title[:20]}'


class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='documents', verbose_name='Проект')
    file = models.FileField(upload_to='documents/%Y/%m/%d/', verbose_name='Файл')
    description = models.CharField('Описание', max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'

    def __str__(self):
        return f'{self.project.title} — {self.description}'

class ProjectVote(models.Model):
    """Голос пользователя за проект: один пользователь — один голос."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='project_votes', verbose_name='Проект')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='project_votes', verbose_name='Пользователь')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Голос'
        verbose_name_plural = 'Голоса'
        unique_together = ['project', 'user']

    def __str__(self):
        return f'{self.user.username} → {self.project.title}'


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='notifications', verbose_name='Получатель')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True,
                              related_name='+', verbose_name='Инициатор')
    text = models.CharField('Текст', max_length=300)
    url = models.CharField('Ссылка', max_length=300, blank=True, default='')
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read'])]

    def __str__(self):
        return f'{self.recipient.username}: {self.text}'


class StatusChange(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='status_history', verbose_name='Проект')
    old_status = models.CharField('Было', max_length=20, blank=True, default='')
    new_status = models.CharField('Стало', max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True,
                                   related_name='+', verbose_name='Кто изменил')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Смена статуса'
        verbose_name_plural = 'История статусов'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['project'])]

    def get_old_display(self):
        return dict(Project.STATUS_CHOICES).get(self.old_status, '—')

    def get_new_display(self):
        return dict(Project.STATUS_CHOICES).get(self.new_status, self.new_status)


class ExpertAssignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='expert_assignments', verbose_name='Проект')
    expert = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='expert_assignments', verbose_name='Эксперт')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True,
                                    related_name='+', verbose_name='Назначил')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Назначение эксперта'
        verbose_name_plural = 'Назначения экспертов'
        unique_together = ['project', 'expert']

    def progress(self):
        total = self.project.contest.criteria.count()
        done = Evaluation.objects.filter(project=self.project, expert=self.expert).count()
        return {'done': done, 'total': total,
                'percent': round(done / total * 100) if total else 0}


class TeamInvite(models.Model):
    STATUS_CHOICES = [('pending', 'Ожидает'), ('accepted', 'Принято'), ('declined', 'Отклонено')]
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                related_name='team_invites', verbose_name='Проект')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='team_invites', verbose_name='Приглашённый')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='+', verbose_name='Пригласил')
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Приглашение в команду'
        verbose_name_plural = 'Приглашения в команду'
        unique_together = ['project', 'user']


class Achievement(models.Model):
    code = models.SlugField('Код', unique=True)
    title = models.CharField('Название', max_length=100)
    description = models.CharField('Описание', max_length=200)
    icon = models.CharField('Иконка', max_length=40, default='bi-star')

    class Meta:
        verbose_name = 'Достижение'
        verbose_name_plural = 'Достижения'

    def __str__(self):
        return self.title


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='achievements', verbose_name='Пользователь')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE,
                                    related_name='earned', verbose_name='Достижение')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Достижение пользователя'
        verbose_name_plural = 'Достижения пользователей'
        unique_together = ['user', 'achievement']
