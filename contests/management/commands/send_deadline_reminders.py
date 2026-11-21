"""Напоминания о дедлайнах: python3 manage.py send_deadline_reminders (cron)."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse

from contests.models import Contest
from contests.services import notify


class Command(BaseCommand):
    help = 'Уведомляет участников конкурсов, до конца приёма которых осталось <= 3 дней'

    def handle(self, *args, **options):
        today = timezone.localdate()
        soon = Contest.objects.filter(is_active=True, results_finalized=False,
                                      end_date__gte=today,
                                      end_date__lte=today + timedelta(days=3))
        sent = 0
        for contest in soon:
            days = (contest.end_date - today).days
            participants = {p.participant for p in contest.projects.exclude(status='draft')}
            notify(participants, None,
                   f'До конца приёма заявок на «{contest.name}» осталось {days} дн. Успейте подать проект!',
                   reverse('contest_detail', args=[contest.pk]))
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Напоминаний отправлено по конкурсам: {sent}'))
