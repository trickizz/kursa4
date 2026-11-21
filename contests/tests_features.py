"""Тесты новых функций: уведомления, команды, эксперты, итоги, PDF, API, ачивки, дедлайны."""
import io
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import (Contest, Project, Criterion, Evaluation, Comment, Notification,
                     StatusChange, ExpertAssignment, TeamInvite, Achievement,
                     UserAchievement, ProjectVote, Document)
from .roles import set_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT, ROLE_ORGANIZER, ROLE_ADMIN
from .services import set_project_status, award

MEDIA = tempfile.mkdtemp()


def make_user(username, role):
    user = User.objects.create_user(username, password='TestPass123!', email=f'{username}@x.com')
    if role:
        set_role(user, role)
    return user


def png_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (60, 40), (99, 102, 241)).save(buf, format='PNG')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, RATELIMIT_ENABLE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class FeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user('boss', ROLE_ADMIN)
        cls.org = make_user('org', ROLE_ORGANIZER)
        cls.exp = make_user('exp', ROLE_EXPERT)
        cls.exp2 = make_user('exp2', ROLE_EXPERT)
        cls.mentor = make_user('mentor', ROLE_MENTOR)
        cls.stud = make_user('stud', ROLE_PARTICIPANT)
        cls.stud2 = make_user('stud2', ROLE_PARTICIPANT)
        cls.contest = Contest.objects.create(name='C1', description='d',
            start_date=date.today(), end_date=date.today() + timedelta(days=20), organizer=cls.org)
        cls.cr1 = Criterion.objects.create(contest=cls.contest, name='K1', max_score=10)
        cls.cr2 = Criterion.objects.create(contest=cls.contest, name='K2', max_score=5)
        cls.proj = Project.objects.create(title='P1', summary='s', contest=cls.contest,
                                          participant=cls.stud, status='submitted')

    def login(self, u):
        self.client.force_login(u)

    def test_score_percent_normalization(self):
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=8)
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr2, score=4)
        # 8/10=80%, 4/5=80% → 80.0
        self.assertEqual(self.proj.score_percent(), 80.0)

    def test_deadline_blocks_submit(self):
        closed = Contest.objects.create(name='Closed', description='d',
            start_date=date.today() - timedelta(days=30), end_date=date.today() - timedelta(days=1), organizer=self.org)
        p = Project.objects.create(title='Late', summary='s', contest=closed, participant=self.stud)
        self.login(self.stud)
        self.assertRedirects(self.client.post(reverse('project_submit', args=[p.pk])),
                             reverse('project_detail', args=[p.pk]), fetch_redirect_response=False)
        p.refresh_from_db()
        self.assertEqual(p.status, 'draft')

    def test_password_reset_sends_email(self):
        r = self.client.post(reverse('password_reset'), {'email': 'stud@x.com'})
        self.assertRedirects(r, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('stud@x.com', mail.outbox[0].to)

    def test_expert_assignment_restricts(self):
        ExpertAssignment.objects.create(project=self.proj, expert=self.exp, assigned_by=self.org)
        self.login(self.exp2)
        r = self.client.post(reverse('evaluation_create'),
                             {'project': self.proj.pk, 'criterion': self.cr1.pk, 'score': 5})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evaluation.objects.count(), 0)
        self.login(self.exp)
        self.client.post(reverse('evaluation_create'),
                         {'project': self.proj.pk, 'criterion': self.cr1.pk, 'score': 5})
        self.assertEqual(Evaluation.objects.count(), 1)
        a = ExpertAssignment.objects.get(project=self.proj, expert=self.exp)
        self.assertEqual(a.progress()['done'], 1)
        self.assertEqual(a.progress()['total'], 2)

    def test_notifications_on_events(self):
        self.login(self.org)
        self.client.post(reverse('change_status', args=[self.proj.pk]), {'status': 'selected'})
        self.assertTrue(Notification.objects.filter(recipient=self.stud).exists())
        self.login(self.exp)
        self.client.post(reverse('evaluation_create'),
                         {'project': self.proj.pk, 'criterion': self.cr1.pk, 'score': 7})
        self.assertTrue(Notification.objects.filter(recipient=self.stud, text__icontains='оценил').exists())

    def test_notification_read(self):
        n = Notification.objects.create(recipient=self.stud, text='t', url='/')
        self.login(self.stud)
        self.client.get(reverse('notification_go', args=[n.pk]))
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        Notification.objects.create(recipient=self.stud, text='t2')
        self.client.post(reverse('notifications_read_all'), {'next': '/'})
        self.assertEqual(Notification.objects.filter(recipient=self.stud, is_read=False).count(), 0)

    def test_status_history_logged(self):
        self.login(self.org)
        self.client.post(reverse('change_status', args=[self.proj.pk]), {'status': 'under_review'})
        h = StatusChange.objects.filter(project=self.proj).first()
        self.assertEqual(h.old_status, 'submitted')
        self.assertEqual(h.new_status, 'under_review')
        self.assertEqual(h.changed_by, self.org)

    def test_leaderboard_and_finalize(self):
        p2 = Project.objects.create(title='P2', summary='s', contest=self.contest,
                                    participant=self.stud2, status='selected')
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=9)
        Evaluation.objects.create(project=p2, expert=self.exp, criterion=self.cr1, score=3)
        self.login(self.org)
        r = self.client.get(reverse('contest_results', args=[self.contest.pk]))
        self.assertEqual(r.context['ranked'][0].title, 'P1')
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.contest.refresh_from_db()
        self.assertTrue(self.contest.results_finalized)
        self.assertFalse(self.contest.is_active)
        p2.refresh_from_db()
        self.assertEqual(p2.status, 'completed')
        self.assertTrue(UserAchievement.objects.filter(user=self.stud, achievement__code='winner').exists())

    def test_pdf_protocol(self):
        self.login(self.org)
        r = self.client.get(reverse('contest_results_pdf', args=[self.contest.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_cover_upload(self):
        self.login(self.stud)
        p = Project.objects.create(title='Cov', summary='s', contest=self.contest, participant=self.stud)
        f = SimpleUploadedFile('cover.png', png_bytes(), content_type='image/png')
        self.client.post(reverse('project_edit', args=[p.pk]),
                         {'title': 'Cov', 'summary': 's', 'contest': self.contest.pk, 'cover': f})
        p.refresh_from_db()
        self.assertTrue(p.cover)

    def test_threaded_comment_and_mention(self):
        self.login(self.mentor)
        r = self.client.post(reverse('add_comment_ajax', args=[self.proj.pk]), {'text': 'Привет @stud'})
        cid = r.json()['comment']['id']
        r2 = self.client.post(reverse('add_comment_ajax', args=[self.proj.pk]),
                              {'text': 'ответ', 'parent_id': cid})
        self.assertEqual(r2.json()['comment']['parent_id'], cid)
        self.assertEqual(Comment.objects.get(pk=r2.json()['comment']['id']).parent_id, cid)
        self.assertTrue(Notification.objects.filter(recipient=self.stud, text__icontains='комментарий').exists())

    def test_dark_theme_present(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('theme-toggle', html)
        self.assertIn('data-theme', html)

    def test_team_invite_accept(self):
        self.login(self.stud)
        self.client.post(reverse('invite_team_member', args=[self.proj.pk]), {'username': 'stud2'})
        inv = TeamInvite.objects.get(project=self.proj, user=self.stud2)
        self.assertTrue(Notification.objects.filter(recipient=self.stud2).exists())
        self.login(self.stud2)
        self.client.post(reverse('respond_team_invite', args=[inv.pk]), {'action': 'accept'})
        self.assertTrue(self.proj.team.filter(pk=self.stud2.pk).exists())
        # соавтор не может голосовать за свой командный проект
        r = self.client.post(reverse('vote_project', args=[self.proj.pk]))
        self.assertEqual(r.status_code, 400)
        # соавтор может грузить документы
        self.assertEqual(self.client.get(reverse('document_upload', args=[self.proj.pk])).status_code, 200)

    def test_achievements_awarded(self):
        self.login(self.stud)
        self.client.post(reverse('project_create'), {'title': 'New', 'summary': 's', 'contest': self.contest.pk})
        self.assertTrue(UserAchievement.objects.filter(user=self.stud, achievement__code='debut').exists())
        award(self.stud, 'debut')  # повторно не дублируется
        self.assertEqual(UserAchievement.objects.filter(user=self.stud, achievement__code='debut').count(), 1)

    def test_profile_shows_achievements(self):
        award(self.stud, 'voter')
        self.login(self.stud)
        html = self.client.get(reverse('profile')).content.decode()
        self.assertIn('Достижения', html)
        self.assertIn('Голос народа', html)

    def test_rating_page(self):
        self.assertEqual(self.client.get(reverse('rating')).status_code, 200)

    # ------------------------------------------------------------- API
    def test_api_list_and_retrieve(self):
        r = self.client.get('/api/contests/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('results', r.json())
        r = self.client.get(f'/api/projects/{self.proj.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['title'], 'P1')

    def test_api_token_and_me(self):
        r = self.client.post('/api/token/', {'username': 'stud', 'password': 'TestPass123!'})
        self.assertEqual(r.status_code, 200)
        token = r.json()['token']
        r = self.client.get('/api/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(r.json()['username'], 'stud')
        self.assertEqual(r.json()['role'], 'Participant')

    def test_api_vote(self):
        self.login(self.stud2)
        r = self.client.post(f'/api/projects/{self.proj.pk}/vote/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['voted'])

    def test_api_create_project(self):
        self.login(self.stud)
        r = self.client.post('/api/projects/', {'title': 'API proj', 'summary': 's', 'contest': self.contest.pk})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Project.objects.get(title='API proj').participant, self.stud)

    def test_api_docs(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)

    def test_mentionize_filter(self):
        from contests.templatetags.query_utils import mentionize
        out = mentionize('hi @stud <b>')
        self.assertIn('<span class="mention">@stud</span>', out)
        self.assertIn('&lt;b&gt;', out)
