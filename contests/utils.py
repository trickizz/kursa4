import csv
from io import TextIOWrapper
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Project, Evaluation, Contest
from .roles import is_organizer


def export_projects_csv(queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="projects.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['ID', 'Название', 'Конкурс', 'Участник',
                     'Наставник', 'Статус', 'Средний балл', 'Голоса'])
    for p in queryset:
        writer.writerow([
            p.id, p.title, p.contest.name, p.participant.username,
            p.mentor.username if p.mentor else '—',
            p.get_status_display(), p.average_score(), p.votes,
        ])
    return response


def export_evaluations_csv(queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="evaluations.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Проект', 'Эксперт', 'Критерий', 'Балл',
                     'Комментарий', 'Дата'])
    for e in queryset:
        writer.writerow([
            e.project.title, e.expert.username, e.criterion.name,
            e.score, e.comment, e.created_at.strftime('%d.%m.%Y'),
        ])
    return response


@login_required
def import_projects_csv(request):
    """Импорт проектов из CSV (доступен организаторам и администраторам)."""
    if not is_organizer(request.user):
        messages.error(request, 'Нет прав для импорта')
        return redirect('project_list')

    if request.method == 'POST' and request.FILES.get('csv_file'):
        try:
            csv_file = TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8-sig')
            sample = csv_file.read(2048)
            csv_file.seek(0)
            delimiter = ',' if sample.count(',') > sample.count(';') else ';'
            reader = csv.DictReader(csv_file, delimiter=delimiter)
            valid_statuses = dict(Project.STATUS_CHOICES)
            count, errors = 0, 0
            for row in reader:
                try:
                    contest = Contest.objects.get(name=(row.get('Конкурс') or '').strip())
                    participant = User.objects.get(username=(row.get('Участник') or '').strip())
                    status = (row.get('Статус') or 'draft').strip()
                    if status not in valid_statuses:
                        status = 'draft'
                    Project.objects.create(
                        title=(row.get('Название') or '').strip(),
                        summary=(row.get('Описание') or '').strip(),
                        contest=contest,
                        participant=participant,
                        status=status,
                    )
                    count += 1
                except Exception as exc:
                    errors += 1
                    messages.warning(request, f'Строка пропущена: {exc}')
            if count:
                messages.success(request, f'Импортировано проектов: {count}. Ошибок: {errors}.')
            else:
                messages.error(request, 'Не удалось импортировать ни одного проекта. Проверьте формат файла.')
        except Exception as exc:
            messages.error(request, f'Не удалось прочитать файл: {exc}')
        return redirect('dashboard')
    messages.error(request, 'Выберите CSV-файл для импорта.')
    return redirect('dashboard')
