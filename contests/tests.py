"""Автотесты платформы: роли, права, жизненный цикл проекта, AJAX, CSV."""
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Contest, Project, Criterion, Stage, Evaluation, Comment, Document, ProjectVote
from .roles import (set_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT,
                    ROLE_ORGANIZER, ROLE_ADMIN)

MEDIA = tempfile.mkdtemp()


def make_user(username, role, **extra):
    user = User.objects.create_user(username, password='TestPass123!', **extra)
    if role:
        set_role(user, role)
    return user


@override_settings(MEDIA_ROOT=MEDIA)
class PlatformTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user('boss', ROLE_ADMIN)
        cls.organizer = make_user('org', ROLE_ORGANIZER)
        cls.expert = make_user('exp', ROLE_EXPERT)
        cls.expert2 = make_user('exp2', ROLE_EXPERT)
        cls.mentor = make_user('mentor', ROLE_MENTOR)
        cls.student = make_user('student', ROLE_PARTICIPANT)
        cls.student2 = make_user('student2', ROLE_PARTICIPANT)
        cls.superuser = User.objects.create_superuser('root', password='TestPass123!')

        cls.contest = Contest.objects.create(
            name='Конкурс 2026', description='Тестовый конкурс',
            start_date=date.today(), end_date=date.today() + timedelta(days=30),
            organizer=cls.organizer)
        cls.contest2 = Contest.objects.create(
            name='Другой конкурс', description='Ещё один',
            start_date=date.today(), end_date=date.today() + timedelta(days=10),
            organizer=cls.organizer)
        cls.criterion = Criterion.objects.create(contest=cls.contest, name='Новизна', max_score=10)
        cls.criterion2 = Criterion.objects.create(contest=cls.contest, name='Польза', max_score=5)
        cls.foreign_criterion = Criterion.objects.create(contest=cls.contest2, name='Чужой', max_score=10)
        Stage.objects.create(contest=cls.contest, name='Отбор', order=1,
                             deadline=date.today() + timedelta(days=7))

        cls.draft = Project.objects.create(title='Черновик', summary='s',
                                           contest=cls.contest, participant=cls.student)
        cls.submitted = Project.objects.create(title='Поданный', summary='s',
                                               contest=cls.contest, participant=cls.student,
                                               status='submitted')

    def login(self, user):
        self.client.force_login(user)

    # ------------------------------------------------ роли и регистрация
    def test_registration_assigns_role(self):
        r = self.client.post(reverse('register'), {
            'username': 'newbie', 'email': 'n@example.com', 'first_name': 'N',
            'last_name': 'B', 'role': ROLE_PARTICIPANT,
            'password1': 'SomePass123!', 'password2': 'SomePass123!'})
        self.assertRedirects(r, reverse('login'))
        user = User.objects.get(username='newbie')
        self.assertTrue(user.groups.filter(name=ROLE_PARTICIPANT).exists())

    def test_registration_cannot_pick_admin(self):
        r = self.client.post(reverse('register'), {
            'username': 'hacker', 'email': 'h@example.com', 'role': ROLE_ADMIN,
            'password1': 'SomePass123!', 'password2': 'SomePass123!'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='hacker').exists())

    def test_navbar_shows_role_menu(self):
        self.login(self.student)
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('Мои проекты', html)
        self.assertIn('Участник', html)
        self.assertNotIn(reverse('role_management'), html)
        self.login(self.organizer)
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('Дашборд', html)
        self.assertIn('Организатор', html)
        self.login(self.mentor)
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('Мои подопечные', html)

    def test_role_management_access(self):
        self.login(self.student)
        self.assertRedirects(self.client.get(reverse('role_management')), reverse('home'))
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse('role_management')).status_code, 200)

    def test_admin_changes_role_and_rights_follow(self):
        self.login(self.admin)
        r = self.client.post(reverse('role_management'),
                             {'user_id': self.student.pk, 'role': ROLE_EXPERT})
        self.assertRedirects(r, reverse('role_management'))
        self.student.refresh_from_db()
        self.assertTrue(self.student.groups.filter(name=ROLE_EXPERT).exists())
        self.assertFalse(self.student.groups.filter(name=ROLE_PARTICIPANT).exists())
        # права изменились: оценка доступна, создание проекта — нет
        self.login(self.student)
        self.assertEqual(self.client.get(reverse('evaluation_create')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('project_create')), reverse('home'))

    def test_cannot_change_own_role_or_superuser(self):
        self.login(self.admin)
        self.client.post(reverse('role_management'), {'user_id': self.admin.pk, 'role': ROLE_PARTICIPANT})
        self.assertTrue(self.admin.groups.filter(name=ROLE_ADMIN).exists())
        self.client.post(reverse('role_management'), {'user_id': self.superuser.pk, 'role': ROLE_PARTICIPANT})
        self.assertTrue(self.superuser.is_superuser)

    # ------------------------------------------------ конкурсы
    def test_contest_create_permissions(self):
        self.login(self.student)
        self.assertRedirects(self.client.get(reverse('contest_create')), reverse('home'))
        self.login(self.organizer)
        r = self.client.post(reverse('contest_create'), {
            'name': 'Новый', 'description': 'd',
            'start_date': date.today(), 'end_date': date.today() + timedelta(days=5),
            'is_active': 'on'})
        self.assertRedirects(r, reverse('contest_list'))
        self.assertTrue(Contest.objects.filter(name='Новый', organizer=self.organizer).exists())

    def test_contest_dates_validation(self):
        self.login(self.organizer)
        r = self.client.post(reverse('contest_create'), {
            'name': 'Плохой', 'description': 'd',
            'start_date': date.today(), 'end_date': date.today() - timedelta(days=5)})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Contest.objects.filter(name='Плохой').exists())

    def test_stage_and_criterion_management(self):
        self.login(self.organizer)
        r = self.client.post(reverse('stage_add', args=[self.contest.pk]),
                             {'name': 'Финал', 'order': 2, 'deadline': date.today() + timedelta(days=20)})
        self.assertRedirects(r, reverse('contest_detail', args=[self.contest.pk]))
        self.assertEqual(self.contest.stages.count(), 2)
        r = self.client.post(reverse('criterion_add', args=[self.contest.pk]),
                             {'name': 'Дизайн', 'max_score': 7})
        self.assertTrue(self.contest.criteria.filter(name='Дизайн').exists())
        stage = self.contest.stages.get(name='Финал')
        self.client.post(reverse('stage_delete', args=[stage.pk]))
        self.assertFalse(Stage.objects.filter(pk=stage.pk).exists())

    # ------------------------------------------------ проекты
    def test_project_create_only_participant(self):
        self.login(self.mentor)
        self.assertRedirects(self.client.get(reverse('project_create')), reverse('home'))
        self.login(self.student)
        r = self.client.post(reverse('project_create'),
                             {'title': 'Идея', 'summary': 's', 'contest': self.contest.pk})
        project = Project.objects.get(title='Идея')
        self.assertEqual(project.participant, self.student)
        self.assertEqual(project.status, 'draft')

    def test_draft_hidden_from_others(self):
        url = reverse('project_detail', args=[self.draft.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.student2)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.student)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.login(self.organizer)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_edit_permissions(self):
        url = reverse('project_edit', args=[self.draft.pk])
        self.login(self.student2)
        self.assertRedirects(self.client.get(url), reverse('project_detail', args=[self.draft.pk]))
        self.login(self.student)
        self.assertEqual(self.client.get(url).status_code, 200)
        # после подачи редактирование запрещено автору
        url2 = reverse('project_edit', args=[self.submitted.pk])
        self.assertRedirects(self.client.get(url2), reverse('project_detail', args=[self.submitted.pk]))
        self.login(self.organizer)
        self.assertEqual(self.client.get(url2).status_code, 200)

    def test_submit_only_owner_and_once(self):
        url = reverse('project_submit', args=[self.draft.pk])
        self.login(self.student2)
        self.assertRedirects(self.client.post(url), reverse('project_detail', args=[self.draft.pk]))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, 'draft')
        self.login(self.student)
        self.client.post(url)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, 'submitted')
        # повторно подать нельзя
        self.assertRedirects(self.client.post(url), reverse('project_detail', args=[self.draft.pk]))

    def test_delete_only_owner_or_organizer(self):
        p = Project.objects.create(title='Удаляемый', summary='s',
                                   contest=self.contest, participant=self.student)
        url = reverse('project_delete', args=[p.pk])
        self.login(self.student2)
        self.client.post(url)
        self.assertTrue(Project.objects.filter(pk=p.pk).exists())
        self.login(self.student)
        self.client.post(url)
        self.assertFalse(Project.objects.filter(pk=p.pk).exists())

    # ------------------------------------------------ голосование
    def test_vote_once_and_toggle(self):
        url = reverse('vote_project', args=[self.submitted.pk])
        self.login(self.student2)
        r = self.client.post(url)
        self.assertEqual(r.json()['votes'], 1)
        self.assertTrue(r.json()['voted'])
        r = self.client.post(url)  # второй клик снимает голос
        self.assertEqual(r.json()['votes'], 0)
        self.assertFalse(r.json()['voted'])
        self.assertEqual(ProjectVote.objects.count(), 0)

    def test_cannot_vote_own_project_or_draft(self):
        self.login(self.student)
        r = self.client.post(reverse('vote_project', args=[self.submitted.pk]))
        self.assertEqual(r.status_code, 400)
        self.login(self.student2)
        r = self.client.post(reverse('vote_project', args=[self.draft.pk]))
        self.assertEqual(r.status_code, 400)

    # ------------------------------------------------ статусы и комментарии
    def test_change_status_permissions(self):
        url = reverse('change_status', args=[self.submitted.pk])
        self.login(self.student)
        self.assertEqual(self.client.post(url, {'status': 'selected'}).status_code, 403)
        self.login(self.organizer)
        r = self.client.post(url, {'status': 'selected'})
        self.assertTrue(r.json()['success'])
        self.submitted.refresh_from_db()
        self.assertEqual(self.submitted.status, 'selected')
        self.assertEqual(self.client.post(url, {'status': 'wrong'}).status_code, 400)

    def test_add_comment(self):
        url = reverse('add_comment_ajax', args=[self.submitted.pk])
        self.login(self.mentor)
        self.assertEqual(self.client.post(url, {'text': '  '}).status_code, 400)
        r = self.client.post(url, {'text': 'Отличная идея!'})
        self.assertTrue(r.json()['success'])
        self.assertEqual(Comment.objects.count(), 1)

    # ------------------------------------------------ оценки
    def test_evaluation_flow_and_limits(self):
        url = reverse('evaluation_create')
        self.login(self.student)
        self.assertRedirects(self.client.get(url), reverse('home'))
        self.login(self.expert)
        r = self.client.post(url, {'project': self.submitted.pk,
                                   'criterion': self.criterion.pk, 'score': 8, 'comment': 'ok'})
        self.assertRedirects(r, reverse('project_detail', args=[self.submitted.pk]))
        self.assertEqual(Evaluation.objects.count(), 1)
        # дубликат
        r = self.client.post(url, {'project': self.submitted.pk,
                                   'criterion': self.criterion.pk, 'score': 7})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evaluation.objects.count(), 1)
        # балл выше максимума
        r = self.client.post(url, {'project': self.submitted.pk,
                                   'criterion': self.criterion2.pk, 'score': 99})
        self.assertEqual(Evaluation.objects.count(), 1)
        # критерий чужого конкурса
        r = self.client.post(url, {'project': self.submitted.pk,
                                   'criterion': self.foreign_criterion.pk, 'score': 5})
        self.assertEqual(Evaluation.objects.count(), 1)

    def test_expert_cannot_evaluate_own_project(self):
        p = Project.objects.create(title='Проект эксперта', summary='s',
                                   contest=self.contest, participant=self.expert,
                                   status='submitted')
        self.login(self.expert)
        r = self.client.post(reverse('evaluation_create'),
                             {'project': p.pk, 'criterion': self.criterion.pk, 'score': 5})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evaluation.objects.count(), 0)

    def test_criteria_json(self):
        self.login(self.expert)
        r = self.client.get(reverse('project_criteria_json', args=[self.submitted.pk]))
        ids = [c['id'] for c in r.json()['criteria']]
        self.assertIn(self.criterion.pk, ids)
        self.assertNotIn(self.foreign_criterion.pk, ids)

    # ------------------------------------------------ документы
    def test_document_upload_and_delete(self):
        url = reverse('document_upload', args=[self.submitted.pk])
        self.login(self.student2)
        self.assertRedirects(self.client.get(url), reverse('project_detail', args=[self.submitted.pk]))
        self.login(self.student)
        f = SimpleUploadedFile('plan.txt', b'project plan', content_type='text/plain')
        r = self.client.post(url, {'file': f, 'description': 'План'})
        self.assertRedirects(r, reverse('project_detail', args=[self.submitted.pk]))
        doc = Document.objects.get()
        self.login(self.student2)
        self.client.post(reverse('document_delete', args=[doc.pk]))
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())
        self.login(self.student)
        self.client.post(reverse('document_delete', args=[doc.pk]))
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

    # ------------------------------------------------ наставничество
    def test_assign_mentor(self):
        url = reverse('assign_mentor', args=[self.submitted.pk])
        self.login(self.student)
        self.client.post(url, {'mentor': self.mentor.pk})
        self.submitted.refresh_from_db()
        self.assertIsNone(self.submitted.mentor)
        self.login(self.organizer)
        self.client.post(url, {'mentor': self.mentor.pk})
        self.submitted.refresh_from_db()
        self.assertEqual(self.submitted.mentor, self.mentor)
        # нельзя назначить не-наставника
        self.client.post(url, {'mentor': self.student.pk})
        self.submitted.refresh_from_db()
        self.assertEqual(self.submitted.mentor, self.mentor)
        # у наставника появился подопечный
        self.login(self.mentor)
        html = self.client.get(reverse('my_mentored')).content.decode()
        self.assertIn('Поданный', html)

    # ------------------------------------------------ дашборд и CSV
    def test_dashboard_access(self):
        self.login(self.expert)
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('home'))
        self.login(self.organizer)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_export_csv(self):
        self.login(self.student)
        self.assertRedirects(self.client.get(reverse('export_projects')), reverse('home'))
        self.login(self.organizer)
        r = self.client.get(reverse('export_projects'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('Поданный', r.content.decode('utf-8-sig'))
        r = self.client.get(reverse('export_evaluations'))
        self.assertEqual(r.status_code, 200)

    def test_import_csv(self):
        self.login(self.organizer)
        content = 'Название;Конкурс;Участник;Описание;Статус\nИмпортный;Конкурс 2026;student;из csv;submitted\n'
        f = SimpleUploadedFile('projects.csv', content.encode('utf-8'), content_type='text/csv')
        r = self.client.post(reverse('import_projects'), {'csv_file': f})
        self.assertRedirects(r, reverse('dashboard'))
        p = Project.objects.get(title='Импортный')
        self.assertEqual(p.status, 'submitted')
        self.assertEqual(p.participant, self.student)

    def test_profile_requires_login(self):
        r = self.client.get(reverse('profile'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)
        self.login(self.mentor)
        r = self.client.get(reverse('profile'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('Наставник', r.content.decode())
