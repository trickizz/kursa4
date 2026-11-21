from django.db import migrations

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


def seed(apps, schema_editor):
    Achievement = apps.get_model('contests', 'Achievement')
    for code, title, description, icon in ACHIEVEMENTS:
        Achievement.objects.get_or_create(code=code, defaults={
            'title': title, 'description': description, 'icon': icon})


def unseed(apps, schema_editor):
    Achievement = apps.get_model('contests', 'Achievement')
    Achievement.objects.filter(code__in=[a[0] for a in ACHIEVEMENTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contests', '0005_' + 'achievement_expertassignment_notification_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
