"""Сигналы: инвалидация кэшей дашборда/рейтинга и генерация миниатюр обложек."""
import io

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from PIL import Image

from .models import Project, Contest, Evaluation, ProjectVote, UserAchievement

DASHBOARD_CACHE_KEY = 'dashboard_stats'
RATING_CACHE_KEY = 'rating_rows'


@receiver([post_save, post_delete], sender=Project)
@receiver([post_save, post_delete], sender=Contest)
@receiver([post_save, post_delete], sender=Evaluation)
@receiver([post_save, post_delete], sender=ProjectVote)
@receiver([post_save, post_delete], sender=UserAchievement)
def invalidate_caches(sender, **kwargs):
    cache.delete(DASHBOARD_CACHE_KEY)
    cache.delete(RATING_CACHE_KEY)


def _make_thumb(instance):
    if not instance.cover or instance.cover_thumb:
        return
    try:
        img = Image.open(instance.cover).convert('RGB')
        img.thumbnail((480, 320))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=82)
        base = instance.cover.name.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        instance.cover_thumb.save('thumb_' + base + '.jpg', ContentFile(buf.getvalue()), save=False)
        type(instance).objects.filter(pk=instance.pk).update(cover_thumb=instance.cover_thumb.name)
    except Exception:
        pass


@receiver(post_save, sender=Project)
@receiver(post_save, sender=Contest)
def generate_thumbnail(sender, instance, **kwargs):
    _make_thumb(instance)
