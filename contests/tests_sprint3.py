"""Тесты спринта 3: паритет API (заморозка/снапшот/веса), рейтинг без N+1,
безопасность медиа, PDF, тосты/SSE-контракт, троттлинг API."""
import io
import os
import tempfile
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (Contest, Project, Criterion, Evaluation, Notification,
                     Achievement, UserAchievement, Tag)
from .roles import set_role, ROLE_PARTICIPANT, ROLE_EXPERT, ROLE_ORGANIZER

MEDIA = tempfile.mkdtemp()


def make_user(username, role):
    u = User.objects.create_user(username, password='TestPass123!', email=f'{username}@x.com')
    if role:
        set_role(u, role)
    return u


@override_settings(MEDIA_ROOT=MEDIA, RATELIMIT_ENABLE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Sprint3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_user('org3', ROLE_ORGANIZER)
        cls.exp = make_user('exp3', ROLE_EXPERT)
        cls.stud = make_user('stud3', ROLE_PARTICIPANT)
        cls.stud2 = make_user('stud3b', ROLE_PARTICIPANT)
        cls.contest = Contest.objects.create(name='C3', description='d',
            start_date=date.today(), end_date=date.today() + timedelta(days=20), organizer=cls.org)
        cls.cr1 = Criterion.objects.create(contest=cls.contest, name='K1', max_score=10, weight=2)
        cls.cr2 = Criterion.objects.create(contest=cls.contest, name='K2', max_score=5, weight=1)
        cls.proj = Project.objects.create(title='P3', summary='s', contest=cls.contest,
                                          participant=cls.stud, status='submitted')

    def setUp(self):
        cache.clear()

    def login(self, u):
        self.client.force_login(u)

    def fully_evaluate(self, project, expert):
        for cr in project.contest.criteria.all():
            Evaluation.objects.get_or_create(project=project, expert=expert, criterion=cr,
                                             defaults={'score': cr.max_score})

    def finalize(self):
        self.fully_evaluate(self.proj, self.exp)
        self.login(self.org)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))

    # ---- API: заморозка и снапшот ----
    def test_api_vote_locked_after_finalize(self):
        self.finalize()
        self.login(self.stud2)
        r = self.client.post(f'/api/projects/{self.proj.pk}/vote/')
        self.assertEqual(r.status_code, 400)

    def test_api_results_use_snapshot(self):
        self.finalize()
        r = self.client.get(f'/api/contests/{self.contest.pk}/results/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['finalized'])
        self.assertEqual(body['results'], self.contest.result_snapshot.data)

    def test_api_results_weighted_live(self):
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=10)
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr2, score=0)
        r = self.client.get(f'/api/contests/{self.contest.pk}/results/')
        self.assertEqual(r.json()['results'][0]['score_percent'], 66.7)

    def test_api_project_tags_and_weighted(self):
        tag = Tag.objects.create(name='веб3')
        self.proj.tags.add(tag)
        r = self.client.get(f'/api/projects/{self.proj.pk}/')
        body = r.json()
        self.assertIn('веб3', body['tags'])
        self.assertIn('weighted_score', body)

    def test_api_filter_by_tag(self):
        tag = Tag.objects.create(name='фильтр3')
        self.proj.tags.add(tag)
        r = self.client.get(f'/api/projects/?tags={tag.pk}')
        self.assertEqual(r.json()['count'], 1)

    # ---- Рейтинг: кэш и корректность очков ----
    def test_rating_cache_invalidated_on_vote(self):
        self.client.get(reverse('rating'))
        self.assertIsNotNone(cache.get('rating_rows'))
        self.login(self.stud2)
        self.client.post(reverse('vote_project', args=[self.proj.pk]))
        self.assertIsNone(cache.get('rating_rows'))

    def test_rating_points_no_join_bug(self):
        Project.objects.filter(pk=self.proj.pk).update(votes=5)
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=10)
        for code in ('debut', 'voter'):
            UserAchievement.objects.create(user=self.stud, achievement=Achievement.objects.get(code=code))
        r = self.client.get(reverse('rating'))
        row = next(x for x in r.context['rows'] if x['user'].pk == self.stud.pk)
        self.assertEqual(row['votes'], 5)
        self.assertEqual(row['projects'], 1)
        self.assertEqual(row['avg_percent'], 100.0)
        # 1*2 + 5 + round(100/10) + 2*3 = 23
        self.assertEqual(row['points'], 23)

    # ---- Безопасность медиа ----
    def test_media_svg_attachment(self):
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        with open(os.path.join(settings.MEDIA_ROOT, 'evil.svg'), 'w') as fh:
            fh.write('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        r = self.client.get('/media/evil.svg')
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')

    def test_media_png_inline_csp(self):
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (10, 10), (99, 102, 241)).save(buf, format='PNG')
        with open(os.path.join(settings.MEDIA_ROOT, 'pic.png'), 'wb') as fh:
            fh.write(buf.getvalue())
        r = self.client.get('/media/pic.png')
        self.assertEqual(r.status_code, 200)
        self.assertIn('inline', r['Content-Disposition'])
        self.assertEqual(r['Content-Security-Policy'], "default-src 'none'")

    def test_media_traversal_and_missing(self):
        self.assertEqual(self.client.get('/media/%2e%2e/secret.txt').status_code, 404)
        self.assertEqual(self.client.get('/media/nope.bin').status_code, 404)

    # ---- PDF ----
    def test_pdf_live(self):
        self.login(self.org)
        r = self.client.get(reverse('contest_results_pdf', args=[self.contest.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_pdf_snapshot_after_finalize(self):
        self.finalize()
        self.login(self.stud)
        r = self.client.get(reverse('contest_results_pdf', args=[self.contest.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    # ---- Сортировка по баллу ----
    def test_sort_score(self):
        r = self.client.get(reverse('project_list') + '?sort=score')
        self.assertEqual(r.status_code, 200)

    # ---- Комментарии: пустой текст ----
    def test_comment_edit_empty_rejected(self):
        from .models import Comment
        c = Comment.objects.create(project=self.proj, author=self.stud, text='hi')
        self.login(self.stud)
        r = self.client.post(reverse('comment_edit', args=[c.pk]), {'text': '   '})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['success'])

    # ---- SSE контракт ----
    def test_sse_payload_keys(self):
        self.login(self.stud)
        Notification.objects.create(recipient=self.stud, text='привет')
        r = self.client.get(reverse('notifications_stream'))
        chunk = next(iter(r.streaming_content)).decode()
        r.close()
        self.assertIn('"unread"', chunk)
        self.assertIn('"latest_id"', chunk)

    # ---- Троттлинг API ----
    def test_api_throttle(self):
        from unittest import mock
        from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
        rates = {'anon': '3/min', 'user': '3/min'}
        with mock.patch.object(AnonRateThrottle, 'THROTTLE_RATES', rates), \
             mock.patch.object(UserRateThrottle, 'THROTTLE_RATES', rates):
            for _ in range(3):
                self.assertEqual(self.client.get('/api/projects/').status_code, 200)
            self.assertEqual(self.client.get('/api/projects/').status_code, 429)
