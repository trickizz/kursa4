"""Демо-данные для защиты курсовой: python3 manage.py seed_demo"""
import io
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from PIL import Image, ImageDraw

from contests.models import (Contest, Stage, Criterion, Project, Evaluation,
                             Comment, ProjectVote, ExpertAssignment, TeamInvite,
                             Tag, Appeal, MentorTask)
from contests.roles import (set_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT,
                            ROLE_ORGANIZER)
from contests.services import award, set_project_status, notify


def gradient_cover(c1, c2, label=''):
    img = Image.new('RGB', (800, 450), c1)
    d = ImageDraw.Draw(img)
    for y in range(450):
        t = y / 450
        d.line([(0, y), (800, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    d.ellipse([560, -80, 820, 180], fill=tuple(min(255, v + 30) for v in c2))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Создаёт демо-пользователей, конкурсы, проекты, оценки, команды и достижения'

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Демо-данные уже созданы.'))
            return

        User.objects.create_superuser('admin', 'admin@example.com', 'Admin12345!',
                                      first_name='Админ', last_name='Платформы')
        users = {}
        for username, role, first, last in [
            ('organizer', ROLE_ORGANIZER, 'Ольга', 'Организаторова'),
            ('expert', ROLE_EXPERT, 'Егор', 'Экспертов'),
            ('expert2', ROLE_EXPERT, 'Елена', 'Оценкина'),
            ('mentor', ROLE_MENTOR, 'Михаил', 'Наставников'),
            ('student', ROLE_PARTICIPANT, 'Иван', 'Студентов'),
            ('student2', ROLE_PARTICIPANT, 'Анна', 'Участникова'),
        ]:
            u = User.objects.create_user(username, f'{username}@example.com', 'Demo12345!',
                                         first_name=first, last_name=last)
            set_role(u, role)
            users[username] = u

        today = date.today()
        c1 = Contest.objects.create(
            name='Цифровые решения 2026',
            description='Конкурс IT-проектов: веб-сервисы, мобильные приложения и умные устройства для города и университета.',
            start_date=today - timedelta(days=10), end_date=today + timedelta(days=40),
            organizer=users['organizer'])
        c2 = Contest.objects.create(
            name='Эко-инициативы',
            description='Конкурс социальных и экологических проектов: раздельный сбор, энергосбережение, зелёный кампус.',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=60),
            organizer=users['organizer'])
        c1.cover.save('cover_digital.png', ContentFile(gradient_cover((99, 102, 241), (217, 70, 239))), save=True)
        c2.cover.save('cover_eco.png', ContentFile(gradient_cover((16, 185, 129), (6, 182, 212))), save=True)

        for i, (name, days) in enumerate([('Приём заявок', 10), ('Экспертиза', 25), ('Финал и награждение', 40)], 1):
            Stage.objects.create(contest=c1, name=name, order=i, deadline=today + timedelta(days=days),
                                 description=f'Этап {i}: {name.lower()}.')
        Stage.objects.create(contest=c2, name='Приём заявок', order=1, deadline=today + timedelta(days=30))

        cr = {}
        for contest, name, mx in [(c1, 'Новизна идеи', 10), (c1, 'Техническая реализация', 10),
                                  (c1, 'Польза для людей', 5), (c2, 'Экологический эффект', 10),
                                  (c2, 'Реализуемость', 5)]:
            cr[(contest.pk, name)] = Criterion.objects.create(contest=contest, name=name, max_score=mx)

        data = [
            ('Умное расписание', 'Веб-сервис, который составляет расписание занятий с учётом пожеланий студентов и нагрузки преподавателей.', c1, 'student', 'submitted', 'mentor', (99, 102, 241), (139, 92, 246)),
            ('Кампус-навигатор', 'Мобильное приложение с картой корпусов, аудиторий и маршрутами для первокурсников.', c1, 'student2', 'under_review', 'mentor', (14, 165, 233), (99, 102, 241)),
            ('ЭкоБокс', 'Сеть умных контейнеров для раздельного сбора мусора с бонусами за переработку.', c2, 'student2', 'selected', None, (16, 185, 129), (245, 158, 11)),
            ('Зелёный кампус', 'Платформа мониторинга энергопотребления корпусов университета.', c2, 'student', 'draft', None, (34, 197, 94), (16, 185, 129)),
        ]
        objs = []
        for title, summary, contest, participant, status, mentor, col1, col2 in data:
            p = Project.objects.create(title=title, summary=summary, contest=contest,
                                       participant=users[participant], status='draft',
                                       mentor=users[mentor] if mentor else None)
            p.cover.save(f'cover_{p.pk}.png', ContentFile(gradient_cover(col1, col2)), save=True)
            if status != 'draft':
                set_project_status(p, status, users['organizer'])
            objs.append(p)

        # команда: student2 — соавтор «Умного расписания»
        objs[0].team.add(users['student2'])
        TeamInvite.objects.create(project=objs[0], user=users['student2'],
                                  invited_by=users['student'], status='accepted')

        # назначения экспертов
        ExpertAssignment.objects.create(project=objs[0], expert=users['expert'], assigned_by=users['organizer'])
        ExpertAssignment.objects.create(project=objs[0], expert=users['expert2'], assigned_by=users['organizer'])
        ExpertAssignment.objects.create(project=objs[1], expert=users['expert'], assigned_by=users['organizer'])

        Evaluation.objects.create(project=objs[0], expert=users['expert'],
                                  criterion=cr[(c1.pk, 'Новизна идеи')], score=8,
                                  comment='Интересная идея, есть аналоги — важно показать отличия.')
        Evaluation.objects.create(project=objs[0], expert=users['expert2'],
                                  criterion=cr[(c1.pk, 'Техническая реализация')], score=7,
                                  comment='Хороший стек технологий, не хватает тестов.')
        Evaluation.objects.create(project=objs[1], expert=users['expert'],
                                  criterion=cr[(c1.pk, 'Польза для людей')], score=5,
                                  comment='Первокурсники точно оценят!')
        Evaluation.objects.create(project=objs[2], expert=users['expert2'],
                                  criterion=cr[(c2.pk, 'Экологический эффект')], score=9,
                                  comment='Отличный потенциал для города.')

        Comment.objects.create(project=objs[0], author=users['mentor'],
                               text='Советую добавить сравнение с существующими решениями в описание. @student')
        Comment.objects.create(project=objs[0], author=users['organizer'],
                               text='Проект принят на экспертизу, ждите оценок.')
        Comment.objects.create(project=objs[1], author=users['expert'],
                               text='Приложите, пожалуйста, макеты экранов.')

        for p, voters in [(objs[0], ['expert', 'expert2', 'student2']),
                          (objs[1], ['student', 'mentor']),
                          (objs[2], ['student', 'expert', 'mentor', 'organizer'])]:
            for v in voters:
                ProjectVote.objects.create(project=p, user=users[v])
            p.votes = p.project_votes.count()
            p.save(update_fields=['votes'])

        # теги, веса критериев, чек-лист наставника, апелляция (демо спринта 2)
        for (cid, name), criterion in cr.items():
            criterion.weight = 2 if ('Новизна' in name or 'Экологический' in name) else 1
            criterion.save(update_fields=['weight'])
        web, _ = Tag.objects.get_or_create(name='веб')
        ai, _ = Tag.objects.get_or_create(name='ИИ')
        eco, _ = Tag.objects.get_or_create(name='экология')
        mobile, _ = Tag.objects.get_or_create(name='мобильное')
        objs[0].tags.add(web, ai)
        objs[1].tags.add(mobile, web)
        objs[2].tags.add(eco)
        MentorTask.objects.create(project=objs[0], mentor=users['mentor'], text='Добавить сравнение с аналогами')
        MentorTask.objects.create(project=objs[0], mentor=users['mentor'], text='Подготовить презентацию', done=True)
        ev = Evaluation.objects.filter(project=objs[0]).first()
        if ev:
            Appeal.objects.create(project=objs[0], evaluation=ev, author=users['student'],
                                  reason='Просим пересмотреть оценку по новизне.', status='open')

        # достижения
        award(users['student'], 'debut')
        award(users['student'], 'submitted')
        award(users['student2'], 'debut')
        award(users['expert'], 'critic')
        award(users['expert2'], 'critic')
        award(users['mentor'], 'mentor_start')
        for u in users.values():
            award(u, 'voter')
        notify(users['student'], users['organizer'],
               'Добро пожаловать на платформу! Загрузите документы к проекту.', '/')

        self.stdout.write(self.style.SUCCESS('Демо-данные созданы!'))
        self.stdout.write('Админ: admin / Admin12345!')
        self.stdout.write('Остальные: organizer, expert, expert2, mentor, student, student2 / Demo12345!')
