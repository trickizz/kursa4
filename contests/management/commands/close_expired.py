"""Автозакрытие конкурсов с истёкшим дедлайном: python3 manage.py close_expired (cron)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from contests.models import Contest


class Command(BaseCommand):
    help = 'Закрывает приём заявок у конкурсов, у которых прошла дата окончания'

    def handle(self, *args, **options):
        expired = Contest.objects.filter(is_active=True, results_finalized=False,
                                         end_date__lt=timezone.localdate())
        count = expired.update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'Закрыто конкурсов: {count}'))
