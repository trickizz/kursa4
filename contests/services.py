"""Бизнес-логика: уведомления, смена статусов с аудитом, достижения, @упоминания."""
import re

from django.contrib.auth.models import User
from django.urls import reverse

from .models import (Notification, StatusChange, Achievement, UserAchievement,
                     Project)

ACHIEVEMENTS = [
    ('debut', 'Дебют', 'Создан первый проект', 'bi-rocket'),
    ('submitted', 'Заявка подана', 'Проект впервые отправлен на конкурс', 'bi-send'),
    ('critic', 'Первая оценка', 'Выставлена первая экспертная оценка', 'bi-clipboard-check'),
    ('voter', 'Голос народа', 'Отдан первый голос за проект', 'bi-heart'),
    ('talker', 'Комментатор', 'Оставлен первый комментарий', 'bi-chat-dots'),
    ('mentor_start', 'Наставник', 'Появился первый подопечный проект', 'bi-mortarboard'),
    ('finalist', 'Финалист', 'Проект доведён до статуса «Завершён»', 'bi-flag'),
    ('winner', 'Победитель', 'Первое место в итогах конкурса', 'bi-trophy'),
]


def notify(recipients, actor, text, url=''):
    """Шлёт уведомление одному пользователю или списку. Инициатор сам себе не получает."""
    if recipients is None:
        return
    if isinstance(recipients, User):
        recipients = [recipients]
    objs = []
    for user in recipients:
        if user is None or (actor is not None and user.pk == actor.pk):
            continue
        objs.append(Notification(recipient=user, actor=actor, text=text[:300], url=url))
    if objs:
        Notification.objects.bulk_create(objs)


def set_project_status(project, new_status, user=None):
    """Единая точка смены статуса: сохраняет, пишет аудит, уведомляет команду, даёт ачивки."""
    old = project.status
    if old == new_status:
        return False
    project.status = new_status
    project.save(update_fields=['status', 'updated_at'])
    StatusChange.objects.create(project=project, old_status=old,
                                new_status=new_status, changed_by=user)
    label = dict(Project.STATUS_CHOICES).get(new_status, new_status)
    members = project.all_members()
    notify(members, user,
           f'Статус проекта «{project.title}» изменён на «{label}».',
           reverse('project_detail', args=[project.pk]))
    if new_status == 'completed':
        for member in members:
            award(member, 'finalist')
    return True


def award(user, code):
    """Выдаёт достижение, если его ещё нет, и уведомляет об этом."""
    if user is None:
        return
    achievement = Achievement.objects.filter(code=code).first()
    if achievement is None:
        return
    _, created = UserAchievement.objects.get_or_create(user=user, achievement=achievement)
    if created:
        notify(user, None, f'Новое достижение: «{achievement.title}»!', reverse('profile'))


def parse_mentions(text):
    """Находит @username в тексте комментария."""
    names = set(re.findall(r'@([A-Za-z0-9_]{3,30})', text))
    if not names:
        return []
    return list(User.objects.filter(username__in=names))
