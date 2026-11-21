"""Дополнительные тесты спринта 3: CRUD организатора, команда, импорт/экспорт,
шаблонные теги, seed_demo и граничные ветки представлений."""
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.template import Template, Context
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse

from .models import (Contest, Project, Criterion, Evaluation, Notification,
                     Stage, Document, ExpertAssignment, TeamInvite, Appeal)
from .roles import set_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT, ROLE_ORGANIZER

MEDIA = tempfile.mkdtemp()


def make_user(username, role):
    u = User.objects.create_user(username, password='TestPass123!', email=f'{username}@x.com')
    if role:
        set_role(u, role)
    return u


@override_settings(MEDIA_ROOT=MEDIA, RATELIMIT_ENABLE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Sprint3ExtraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_user('orgX', ROLE_ORGANIZER)
        cls.exp = make_user('expX', ROLE_EXPERT)
        cls.mentor = make_user('mentorX', ROLE_MENTOR)
        cls.stud = make_user('studX', ROLE_PARTICIPANT)
        cls.stud2 = make_user('studX2', ROLE_PARTICIPANT)
        cls.admin = User.objects.create_superuser('adminX', 'a@x.com', 'TestPass123!')
        cls.contest = Contest.objects.create(name='CX', description='d',
            start_date=date.today(), end_date=date.today() + timedelta(days=20), organizer=cls.org)
        cls.cr1 = Criterion.objects.create(contest=cls.contest, name='K1', max_score=10, weight=1)
        cls.proj = Project.objects.create(title='PX', summary='s', contest=cls.contest,
                                          participant=cls.stud, status='submitted')

    def setUp(self):
        cache.clear()

    def login(self, u):
        self.client.force_login(u)

    def test_seed_demo_command(self):
        call_command('seed_demo')
        self.assertTrue(Contest.objects.filter(name='AI-вызов 2026').exists())
        self.assertTrue(User.objects.filter(username='anna').exists())
        self.assertTrue(Project.objects.filter(title='EcoTrack').exists())

    def test_csv_import(self):
        self.login(self.org)
        content = 'Название;Описание;Конкурс;Участник;Статус\nИмпорт1;опис;CX;studX;submitted\nИмпорт2;опис;НетТакого;studX;draft\n'
        f = SimpleUploadedFile('p.csv', content.encode('utf-8-sig'), content_type='text/csv')
        self.client.post(reverse('import_projects'), {'csv_file': f})
        self.assertTrue(Project.objects.filter(title='Импорт1').exists())
        self.assertFalse(Project.objects.filter(title='Импорт2').exists())

    def test_csv_import_denied_and_get(self):
        self.login(self.stud)
        self.assertEqual(self.client.post(reverse('import_projects')).status_code, 302)
        self.login(self.org)
        self.assertEqual(self.client.get(reverse('import_projects')).status_code, 302)

    def test_csv_exports(self):
        self.login(self.org)
        r = self.client.get(reverse('export_projects'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertEqual(self.client.get(reverse('export_evaluations')).status_code, 200)
        self.login(self.stud)
        self.assertEqual(self.client.get(reverse('export_projects')).status_code, 302)
        self.assertEqual(self.client.get(reverse('export_evaluations')).status_code, 302)

    def test_template_tags(self):
        req = RequestFactory().get('/projects/?tag=веб&page=2')
        tpl = Template("{% load query_utils %}{{ text|mentionize }}|{% modify_query page=3 tag='' %}")
        out = tpl.render(Context({'text': 'привет @studX', 'request': req}))
        self.assertIn('mention', out)
        self.assertIn('page=3', out)
        self.assertNotIn('tag=', out)

    def test_list_filters(self):
        self.assertEqual(self.client.get(reverse('contest_list') + '?q=CX').status_code, 200)
        url = reverse('project_list') + f'?contest={self.contest.pk}&status=submitted&q=PX&sort=old'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_contest_update_delete(self):
        self.login(self.org)
        self.client.post(reverse('contest_edit', args=[self.contest.pk]),
                         {'name': 'CX2', 'description': 'd', 'start_date': '2026-01-01',
                          'end_date': '2026-12-31', 'is_active': 'on'})
        self.contest.refresh_from_db()
        self.assertEqual(self.contest.name, 'CX2')
        self.client.post(reverse('contest_delete', args=[self.contest.pk]))
        self.assertFalse(Contest.objects.filter(pk=self.contest.pk).exists())

    def test_stage_criterion_crud(self):
        self.login(self.org)
        self.client.post(reverse('stage_add', args=[self.contest.pk]), {'name': 'Э1', 'order': 1})
        stage = Stage.objects.get(name='Э1')
        self.client.post(reverse('stage_delete', args=[stage.pk]))
        self.assertFalse(Stage.objects.filter(pk=stage.pk).exists())
        self.client.post(reverse('criterion_add', args=[self.contest.pk]),
                         {'name': 'KX', 'max_score': 10, 'weight': 1})
        cr = Criterion.objects.get(name='KX')
        self.client.post(reverse('criterion_delete', args=[cr.pk]))
        self.assertFalse(Criterion.objects.filter(pk=cr.pk).exists())

    def test_stage_criterion_delete_denied(self):
        stage = Stage.objects.create(contest=self.contest, name='Э', order=1)
        self.login(self.stud)
        self.assertEqual(self.client.post(reverse('stage_delete', args=[stage.pk])).status_code, 302)
        self.assertEqual(self.client.post(reverse('criterion_delete', args=[self.cr1.pk])).status_code, 302)
        self.assertTrue(Stage.objects.filter(pk=stage.pk).exists())

    def test_assign_mentor_and_expert(self):
        self.login(self.org)
        self.client.post(reverse('assign_mentor', args=[self.proj.pk]), {'mentor': self.mentor.pk})
        self.proj.refresh_from_db()
        self.assertEqual(self.proj.mentor, self.mentor)
        self.client.post(reverse('assign_mentor', args=[self.proj.pk]), {'mentor': ''})
        self.proj.refresh_from_db()
        self.assertIsNone(self.proj.mentor)
        self.client.post(reverse('assign_expert', args=[self.proj.pk]), {'expert': self.exp.pk})
        asg = ExpertAssignment.objects.get(project=self.proj, expert=self.exp)
        self.client.post(reverse('unassign_expert', args=[asg.pk]))
        self.assertFalse(ExpertAssignment.objects.filter(pk=asg.pk).exists())

    def test_assign_denied(self):
        self.login(self.stud)
        self.assertEqual(self.client.post(reverse('assign_mentor', args=[self.proj.pk]),
                                          {'mentor': self.mentor.pk}).status_code, 302)
        self.assertEqual(self.client.post(reverse('assign_expert', args=[self.proj.pk]),
                                          {'expert': self.exp.pk}).status_code, 302)
        self.assertFalse(ExpertAssignment.objects.exists())

    def test_team_invite_accept(self):
        self.login(self.stud)
        self.client.post(reverse('invite_team_member', args=[self.proj.pk]), {'username': 'studX2'})
        invite = TeamInvite.objects.get(project=self.proj, user=self.stud2)
        self.login(self.stud2)
        self.client.post(reverse('respond_team_invite', args=[invite.pk]), {'action': 'accept'})
        self.assertTrue(self.proj.team.filter(pk=self.stud2.pk).exists())

    def test_team_invite_decline_and_denied(self):
        self.login(self.stud2)
        self.assertEqual(self.client.post(reverse('invite_team_member', args=[self.proj.pk]),
                                          {'username': 'studX'}).status_code, 302)
        self.login(self.stud)
        self.client.post(reverse('invite_team_member', args=[self.proj.pk]), {'username': 'studX2'})
        invite = TeamInvite.objects.get(project=self.proj, user=self.stud2)
        self.login(self.stud2)
        self.client.post(reverse('respond_team_invite', args=[invite.pk]), {'action': 'decline'})
        invite.refresh_from_db()
        self.assertEqual(invite.status, 'declined')

    def test_notifications(self):
        n = Notification.objects.create(recipient=self.stud, text='тест', url='/')
        Notification.objects.create(recipient=self.stud, text='тест2')
        self.login(self.stud)
        self.assertEqual(self.client.get(reverse('notifications')).status_code, 200)
        self.client.get(reverse('notification_go', args=[n.pk]))
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.client.post(reverse('notifications_read_all'), {'next': '/'})
        self.assertFalse(Notification.objects.filter(recipient=self.stud, is_read=False).exists())

    def test_personal_pages(self):
        self.login(self.stud)
        for name in ['my_projects', 'profile']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.login(self.exp)
        self.assertEqual(self.client.get(reverse('my_evaluations')).status_code, 200)
        self.login(self.mentor)
        self.assertEqual(self.client.get(reverse('my_mentored')).status_code, 200)

    def test_finalize_denied_and_repeat(self):
        self.login(self.stud)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.contest.refresh_from_db()
        self.assertFalse(self.contest.results_finalized)
        for cr in self.contest.criteria.all():
            Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=cr, score=cr.max_score)
        self.login(self.org)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.contest.refresh_from_db()
        self.assertTrue(self.contest.results_finalized)

    def test_pdf_denied_before_finalize(self):
        self.login(self.stud)
        self.assertEqual(self.client.get(reverse('contest_results_pdf', args=[self.contest.pk])).status_code, 302)

    def test_rating_cache_hit(self):
        self.assertEqual(self.client.get(reverse('rating')).status_code, 200)
        self.assertEqual(self.client.get(reverse('rating')).status_code, 200)

    def test_comment_too_long(self):
        self.login(self.stud)
        r = self.client.post(reverse('add_comment_ajax', args=[self.proj.pk]), {'text': 'x' * 2001})
        self.assertEqual(r.status_code, 400)

    def test_change_status_denied(self):
        self.login(self.stud)
        r = self.client.post(reverse('change_status', args=[self.proj.pk]), {'status': 'selected'})
        self.assertEqual(r.status_code, 403)

    def test_register_authenticated_redirect(self):
        self.login(self.stud)
        self.assertEqual(self.client.get(reverse('register')).status_code, 302)

    def test_role_management(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse('role_management') + '?q=stud').status_code, 200)
        self.client.post(reverse('role_management'), {'user_id': self.stud.pk, 'role': ROLE_MENTOR})
        self.assertTrue(self.stud.groups.filter(name=ROLE_MENTOR).exists())
        self.client.post(reverse('role_management'), {'user_id': self.admin.pk, 'role': ROLE_MENTOR})
        self.client.post(reverse('role_management'), {})

    def test_document_upload_delete(self):
        self.login(self.stud)
        f = SimpleUploadedFile('d.txt', b'hi', content_type='text/plain')
        self.client.post(reverse('document_upload', args=[self.proj.pk]), {'file': f, 'description': 'x'})
        doc = Document.objects.get(project=self.proj)
        self.client.post(reverse('document_delete', args=[doc.pk]))
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

    def test_project_delete(self):
        self.login(self.stud)
        self.client.post(reverse('project_delete', args=[self.proj.pk]))
        self.assertFalse(Project.objects.filter(pk=self.proj.pk).exists())

    def test_evaluation_create(self):
        ExpertAssignment.objects.create(project=self.proj, expert=self.exp, assigned_by=self.org)
        self.login(self.exp)
        self.assertEqual(self.client.get(reverse('evaluation_create') + f'?project={self.proj.pk}').status_code, 200)
        self.client.post(reverse('evaluation_create'),
                         {'project': self.proj.pk, 'criterion': self.cr1.pk, 'score': 7, 'comment': 'ok'})
        self.assertTrue(Evaluation.objects.filter(project=self.proj, expert=self.exp, score=7).exists())

    def test_appeal_denied_branches(self):
        ev = Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=3)
        self.login(self.stud2)
        self.assertEqual(self.client.post(reverse('appeal_create', args=[self.proj.pk]),
                                          {'evaluation': ev.pk, 'reason': 'x'}).status_code, 302)
        self.login(self.stud)
        self.client.post(reverse('appeal_create', args=[self.proj.pk]), {'evaluation': ev.pk, 'reason': 'причина'})
        appeal = Appeal.objects.get()
        self.assertEqual(self.client.post(reverse('appeal_resolve', args=[appeal.pk]),
                                          {'status': 'accepted', 'resolution': 'r'}).status_code, 302)

    def test_clone_denied(self):
        self.login(self.stud)
        self.assertEqual(self.client.post(reverse('contest_clone', args=[self.contest.pk])).status_code, 302)
        self.assertFalse(Contest.objects.filter(name__icontains='копия').exists())
