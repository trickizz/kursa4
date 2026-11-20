from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


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

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('project_detail', args=[self.pk])

    def average_score(self):
        evaluations = self.evaluations.all()
        if evaluations:
            return round(sum(e.score for e in evaluations) / evaluations.count(), 2)
        return 0


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