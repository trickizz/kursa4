import csv
from io import TextIOWrapper
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Project, Evaluation, Contest


def export_projects_csv(queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="projects.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['ID', 'Название', 'Конкурс', 'Участник',
                     'Наставник', 'Статус', 'Средний балл'])
    for p in queryset:
        writer.writerow([
            p.id, p.title, p.contest.name, p.participant.username,
            p.mentor.username if p.mentor else '—',
            p.get_status_display(), p.average_score()
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
            e.score, e.comment, e.created_at.strftime('%d.%m.%Y')
        ])
    return response


@login_required
def import_projects_csv(request):
    if not (request.user.is_superuser or
            request.user.groups.filter(name__in=['Organizer', 'Admin']).exists()):
        messages.error(request, 'Нет прав для импорта')
        return redirect('project_list')

    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8-sig')
        reader = csv.DictReader(csv_file, delimiter=';')
        count = 0
        for row in reader:
            try:
                contest = Contest.objects.get(name=row['Конкурс'])
                participant = User.objects.get(username=row['Участник'])
                Project.objects.create(
                    title=row['Название'],
                    summary=row.get('Описание', ''),
                    contest=contest,
                    participant=participant,
                    status=row.get('Статус', 'draft'),
                )
                count += 1
            except Exception as e:
                messages.warning(request, f'Ошибка: {e}')
        messages.success(request, f'Импортировано {count} проектов')
        return redirect('project_list')
    return redirect('project_list')