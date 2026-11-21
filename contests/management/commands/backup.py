"""Резервная копия данных: python3 manage.py backup."""
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Сохраняет дамп данных (contests + пользователи) в backups/'

    def handle(self, *args, **options):
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        name = datetime.now().strftime('backup_%Y%m%d_%H%M%S.json')
        path = os.path.join(backup_dir, name)
        with open(path, 'w', encoding='utf-8') as fh:
            call_command('dumpdata', 'contests', 'auth.user', 'auth.group',
                         indent=2, stdout=fh)
        self.stdout.write(self.style.SUCCESS(f'Бэкап сохранён: {path}'))
