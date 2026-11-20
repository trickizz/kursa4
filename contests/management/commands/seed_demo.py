"""Демо-данные для защиты курсовой: python3 manage.py seed_demo"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from contests.models import Contest, Stage, Criterion, Project, Evaluation, Comment, ProjectVote
from contests.roles import set_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT, ROLE_ORGANIZER, ROLE_ADMIN


class Command(BaseCommand):
    help = 'Создаёт демо-пользователей, конкурсы и проекты'

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Демо-данные уже созданы.'))
            return

        admin = User.objects.create_superuser('admin', 'admin@example.com', 'Admin12345!',
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

        for i, (name, days) in enumerate([('Приём заявок', 10), ('Экспертиза', 25), ('Финал и награждение', 40)], 1):
            Stage.objects.create(contest=c1, name=name, order=i, deadline=today + timedelta(days=days),
                                 description=f'Этап {i}: {name.lower()}.')
        Stage.objects.create(contest=c2, name='Приём заявок', order=1, deadline=today + timedelta(days=30))

        cr = {}
        for contest, name, mx in [(c1, 'Новизна идеи', 10), (c1, 'Техническая реализация', 10),
                                  (c1, 'Польза для людей', 5), (c2, 'Экологический эффект', 10),
                                  (c2, 'Реализуемость', 5)]:
            cr[(contest.pk, name)] = Criterion.objects.create(contest=contest, name=name, max_score=mx)

        projects = [
            ('Умное расписание', 'Веб-сервис, который составляет расписание занятий с учётом пожеланий студентов и нагрузки преподавателей.', c1, 'student', 'submitted', 'mentor'),
            ('Кампус-навигатор', 'Мобильное приложение с картой корпусов, аудиторий и маршрутами для первокурсников.', c1, 'student2', 'under_review', 'mentor'),
            ('ЭкоБокс', 'Сеть умных контейнеров для раздельного сбора мусора с бонусами за переработку.', c2, 'student2', 'selected', None),
            ('Зелёный кампус', 'Платформа мониторинга энергопотребления корпусов университета.', c2, 'student', 'draft', None),
        ]
        objs = []
        for title, summary, contest, participant, status, mentor in projects:
            p = Project.objects.create(title=title, summary=summary, contest=contest,
                                       participant=users[participant], status=status,
                                       mentor=users[mentor] if mentor else None)
            objs.append(p)

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
                               text='Советую добавить сравнение с существующими решениями в описание.')
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

        self.stdout.write(self.style.SUCCESS('Демо-данные созданы!'))
        self.stdout.write('Админ: admin / Admin12345!')
        self.stdout.write('Остальные: organizer, expert, expert2, mentor, student, student2 / Demo12345!')
