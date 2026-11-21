from django.apps import AppConfig


class ContestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contests'
    verbose_name = 'Конкурсы проектов'

    def ready(self):
        from . import signals  # noqa: F401
