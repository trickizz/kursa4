"""Тесты спринта 2: заморозка, кэш, медиа, апелляции, веса, команды, SSE, XLSX и др."""
import io
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import (Contest, Project, Criterion, Evaluation, Comment, Notification,
                     Appeal, MentorTask, Tag, ResultSnapshot, ExpertAssignment, Document)
from .roles import set_role, ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT, ROLE_ORGANIZER

MEDIA = tempfile.mkdtemp()


def make_user(username, role):
    u = User.objects.create_user(username, password='TestPass123!', email=f'{username}@x.com')
    if role:
        set_role(u, role)
    return u


def png():
    buf = io.BytesIO()
    Image.new('RGB', (50, 40), (99, 102, 241)).save(buf, format='PNG')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, RATELIMIT_ENABLE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Sprint2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_user('org', ROLE_ORGANIZER)
        cls.exp = make_user('exp', ROLE_EXPERT)
        cls.mentor = make_user('mentor', ROLE_MENTOR)
        cls.stud = make_user('stud', ROLE_PARTICIPANT)
        cls.stud2 = make_user('stud2', ROLE_PARTICIPANT)
        cls.contest = Contest.objects.create(name='C', description='d',
            start_date=date.today(), end_date=date.today() + timedelta(days=20), organizer=cls.org)
        cls.cr1 = Criterion.objects.create(contest=cls.contest, name='K1', max_score=10, weight=2)
        cls.cr2 = Criterion.objects.create(contest=cls.contest, name='K2', max_score=5, weight=1)
        cls.proj = Project.objects.create(title='P', summary='s', contest=cls.contest,
                                          participant=cls.stud, status='submitted', mentor=cls.mentor)

    def login(self, u):
        self.client.force_login(u)

    def fully_evaluate(self, project, expert):
        for cr in project.contest.criteria.all():
            Evaluation.objects.get_or_create(project=project, expert=expert, criterion=cr,
                                             defaults={'score': cr.max_score})

    def test_weighted_score(self):
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=10)
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr2, score=0)
        # (10/10*2 + 0/5*1) / (2+1) * 100 = 66.7
        self.assertEqual(self.proj.weighted_score_percent(), 66.7)

    def test_vote_locked_after_finalize(self):
        self.fully_evaluate(self.proj, self.exp)
        self.login(self.org)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.login(self.stud2)
        r = self.client.post(reverse('vote_project', args=[self.proj.pk]))
        self.assertEqual(r.status_code, 400)

    def test_eval_locked_after_finalize(self):
        self.fully_evaluate(self.proj, self.exp)
        self.login(self.org)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        exp2 = make_user('exp2', ROLE_EXPERT)
        self.login(exp2)
        r = self.client.post(reverse('evaluation_create'),
                             {'project': self.proj.pk, 'criterion': self.cr1.pk, 'score': 5})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evaluation.objects.filter(expert=exp2).count(), 0)

    def test_finalize_gate_blocks_incomplete(self):
        Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=5)
        self.login(self.org)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.contest.refresh_from_db()
        self.assertFalse(self.contest.results_finalized)

    def test_finalize_creates_snapshot(self):
        self.fully_evaluate(self.proj, self.exp)
        self.login(self.org)
        self.client.post(reverse('contest_finalize', args=[self.contest.pk]))
        self.assertTrue(ResultSnapshot.objects.filter(contest=self.contest).exists())
        snap = self.contest.result_snapshot.data
        self.assertEqual(snap[0]['title'], 'P')

    def test_cache_invalidation(self):
        from django.core.cache import cache
        cache.set('dashboard_stats', {'x': 1}, 60)
        Project.objects.create(title='New', summary='s', contest=self.contest, participant=self.stud)
        self.assertIsNone(cache.get('dashboard_stats'))

    def test_document_whitelist(self):
        self.login(self.stud)
        bad = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        self.client.post(reverse('document_upload', args=[self.proj.pk]), {'file': bad, 'description': 'x'})
        self.assertEqual(Document.objects.count(), 0)
        good = SimpleUploadedFile('note.txt', b'hello', content_type='text/plain')
        self.client.post(reverse('document_upload', args=[self.proj.pk]), {'file': good, 'description': 'ok'})
        self.assertEqual(Document.objects.count(), 1)

    def test_media_serve_attachment(self):
        self.login(self.stud)
        f = SimpleUploadedFile('note.txt', b'hello', content_type='text/plain')
        self.client.post(reverse('document_upload', args=[self.proj.pk]), {'file': f, 'description': 'ok'})
        doc = Document.objects.first()
        r = self.client.get(doc.file.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])

    def test_comment_edit_delete(self):
        c = Comment.objects.create(project=self.proj, author=self.stud, text='hi')
        self.login(self.stud2)
        r = self.client.post(reverse('comment_edit', args=[c.pk]), {'text': 'hack'})
        self.assertEqual(r.status_code, 403)
        self.login(self.stud)
        r = self.client.post(reverse('comment_edit', args=[c.pk]), {'text': 'edited'})
        self.assertTrue(r.json()['success'])
        c.refresh_from_db()
        self.assertEqual(c.text, 'edited')
        self.login(self.org)
        r = self.client.post(reverse('comment_delete', args=[c.pk]))
        self.assertTrue(r.json()['success'])
        self.assertFalse(Comment.objects.filter(pk=c.pk).exists())

    def test_appeal_flow(self):
        ev = Evaluation.objects.create(project=self.proj, expert=self.exp, criterion=self.cr1, score=3)
        self.login(self.stud)
        self.client.post(reverse('appeal_create', args=[self.proj.pk]), {'evaluation': ev.pk, 'reason': 'несогласен'})
        appeal = Appeal.objects.get()
        self.assertEqual(appeal.status, 'open')
        self.assertTrue(Notification.objects.filter(recipient=self.org, text__icontains='Апелляция').exists())
        self.login(self.org)
        self.client.post(reverse('appeal_resolve', args=[appeal.pk]), {'status': 'accepted', 'resolution': 'пересмотрено'})
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, 'accepted')
        self.assertEqual(appeal.resolved_by, self.org)

    def test_tags_filter_and_sort(self):
        tag = Tag.objects.create(name='веб')
        self.proj.tags.add(tag)
        r = self.client.get(reverse('project_list') + '?tag=веб')
        self.assertEqual(len(r.context['projects']), 1)
        r = self.client.get(reverse('project_list') + '?tag=неттакого')
        self.assertEqual(len(r.context['projects']), 0)
        r = self.client.get(reverse('project_list') + '?sort=votes')
        self.assertEqual(r.status_code, 200)

    def test_contest_clone(self):
        self.login(self.org)
        self.client.post(reverse('contest_clone', args=[self.contest.pk]))
        clone = Contest.objects.get(name='C (копия)')
        self.assertEqual(clone.criteria.count(), 2)
        self.assertEqual(clone.projects.count(), 0)

    def test_bulk_status(self):
        p2 = Project.objects.create(title='P2', summary='s', contest=self.contest, participant=self.stud2, status='submitted')
        self.login(self.org)
        self.client.post(reverse('bulk_action', args=[self.contest.pk]),
                         {'project_ids': [self.proj.pk, p2.pk], 'action': 'status', 'status': 'selected'})
        self.proj.refresh_from_db(); p2.refresh_from_db()
        self.assertEqual(self.proj.status, 'selected')
        self.assertEqual(p2.status, 'selected')

    def test_bulk_expert(self):
        self.login(self.org)
        self.client.post(reverse('bulk_action', args=[self.contest.pk]),
                         {'project_ids': [self.proj.pk], 'action': 'expert', 'expert': self.exp.pk})
        self.assertTrue(ExpertAssignment.objects.filter(project=self.proj, expert=self.exp).exists())

    def test_mentor_tasks(self):
        self.login(self.mentor)
        self.client.post(reverse('mentor_task_add', args=[self.proj.pk]), {'text': 'Добавить тесты'})
        task = MentorTask.objects.get()
        self.login(self.stud)
        r = self.client.post(reverse('mentor_task_toggle', args=[task.pk]))
        self.assertTrue(r.json()['done'])
        self.login(self.mentor)
        self.client.post(reverse('mentor_task_delete', args=[task.pk]))
        self.assertFalse(MentorTask.objects.filter(pk=task.pk).exists())

    def test_email_notification(self):
        mail.outbox = []
        self.login(self.org)
        self.client.post(reverse('change_status', args=[self.proj.pk]), {'status': 'selected'})
        self.assertTrue(any('stud@x.com' in m.to for m in mail.outbox))

    def test_close_expired_command(self):
        old = Contest.objects.create(name='Old', description='d', start_date=date.today() - timedelta(days=30),
                                     end_date=date.today() - timedelta(days=1), organizer=self.org)
        call_command('close_expired')
        old.refresh_from_db()
        self.assertFalse(old.is_active)

    def test_deadline_reminder_command(self):
        mail.outbox = []
        soon = Contest.objects.create(name='Soon', description='d', start_date=date.today(),
                                      end_date=date.today() + timedelta(days=2), organizer=self.org)
        Project.objects.create(title='S', summary='s', contest=soon, participant=self.stud, status='submitted')
        call_command('send_deadline_reminders')
        self.assertTrue(Notification.objects.filter(recipient=self.stud, text__icontains='осталось').exists())

    def test_backup_command(self):
        call_command('backup')
        import os
        from django.conf import settings
        backups = os.listdir(os.path.join(settings.BASE_DIR, 'backups'))
        self.assertTrue(any(b.startswith('backup_') for b in backups))

    def test_healthz(self):
        r = self.client.get(reverse('healthz'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'ok')

    def test_xlsx_export(self):
        self.login(self.org)
        r = self.client.get(reverse('export_xlsx'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertTrue(r.content.startswith(b'PK'))

    def test_thumbnail_generated(self):
        self.login(self.stud)
        p = Project.objects.create(title='T', summary='s', contest=self.contest, participant=self.stud)
        f = SimpleUploadedFile('c.png', png(), content_type='image/png')
        self.client.post(reverse('project_edit', args=[p.pk]), {'title': 'T', 'summary': 's', 'contest': self.contest.pk, 'cover': f, 'tags': ''})
        p.refresh_from_db()
        self.assertTrue(p.cover_thumb)

    def test_sse_stream(self):
        self.login(self.stud)
        r = self.client.get(reverse('notifications_stream'))
        self.assertEqual(r['Content-Type'], 'text/event-stream')
        chunk = next(iter(r.streaming_content))
        self.assertIn(b'data:', chunk)
        r.close()

    def test_api_filter(self):
        r = self.client.get(f'/api/projects/?contest={self.contest.pk}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 1)

    def test_rating_cached(self):
        from django.core.cache import cache
        self.client.get(reverse('rating'))
        self.assertIsNotNone(cache.get('rating_rows'))
