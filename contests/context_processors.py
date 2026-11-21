from .roles import (ROLE_INFO, primary_role, is_site_admin, is_organizer,
                    is_expert, is_mentor, is_participant)
from .models import Notification


def roles(request):
    """Флаги ролей доступны в любом шаблоне: navbar, кнопки, панели."""
    user = getattr(request, 'user', None)
    if user is None:
        return {}
    role = primary_role(user)
    info = ROLE_INFO.get(role, {})
    return {
        'role_key': role,
        'role_label': info.get('label', 'Без роли' if user.is_authenticated else ''),
        'role_icon': info.get('icon', 'bi-person'),
        'role_css': info.get('css', 'role-none'),
        'is_site_admin': is_site_admin(user),
        'can_manage': is_organizer(user),      # организатор / админ / суперюзер
        'is_expert': is_expert(user),
        'is_mentor': is_mentor(user),
        'is_participant': is_participant(user),
    }


def notifications(request):
    """Непрочитанные уведомления для колокольчика в шапке."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    unread = Notification.objects.filter(recipient=user, is_read=False)
    return {'notif_unread': unread.count(), 'notif_recent': unread[:7]}
