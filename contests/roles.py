"""
Единая система ролей приложения.

Роль = группа Django (auth.Group). У пользователя одна основная роль.
Администратор (группа Admin или is_superuser) наследует права всех ролей.
"""
from django.contrib.auth.models import Group

ROLE_PARTICIPANT = 'Participant'
ROLE_MENTOR = 'Mentor'
ROLE_EXPERT = 'Expert'
ROLE_ORGANIZER = 'Organizer'
ROLE_ADMIN = 'Admin'

ALL_ROLES = [ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT, ROLE_ORGANIZER, ROLE_ADMIN]
# Роли, доступные при самостоятельной регистрации
SELF_SIGNUP_ROLES = [ROLE_PARTICIPANT, ROLE_MENTOR, ROLE_EXPERT]

ROLE_INFO = {
    ROLE_PARTICIPANT: {
        'label': 'Участник',
        'icon': 'bi-rocket-takeoff',
        'css': 'role-participant',
        'description': 'Создаёт проекты и подаёт их на конкурсы.',
        'abilities': [
            'Создание и редактирование своих проектов (пока черновик)',
            'Подача проекта на конкурс и загрузка документов',
            'Отслеживание статуса, оценок и комментариев',
            'Голосование за проекты и комментарии',
        ],
    },
    ROLE_MENTOR: {
        'label': 'Наставник',
        'icon': 'bi-mortarboard',
        'css': 'role-mentor',
        'description': 'Помогает участникам дорабатывать проекты.',
        'abilities': [
            'Раздел «Мои подопечные» со списком закреплённых проектов',
            'Загрузка документов в проекты подопечных',
            'Комментарии и рекомендации по проектам',
            'Голосование за проекты',
        ],
    },
    ROLE_EXPERT: {
        'label': 'Эксперт',
        'icon': 'bi-clipboard-check',
        'css': 'role-expert',
        'description': 'Оценивает поданные проекты по критериям конкурса.',
        'abilities': [
            'Выставление оценок по критериям (не выше максимума)',
            'Комментарии к оценкам',
            'Раздел «Мои оценки» со всей историей',
            'Голосование за проекты',
        ],
    },
    ROLE_ORGANIZER: {
        'label': 'Организатор',
        'icon': 'bi-megaphone',
        'css': 'role-organizer',
        'description': 'Проводит конкурсы и управляет ходом отбора.',
        'abilities': [
            'Создание и редактирование конкурсов, этапов и критериев',
            'Смена статусов проектов и назначение наставников',
            'Дашборд со статистикой и графиками',
            'Экспорт и импорт проектов/оценок в CSV',
        ],
    },
    ROLE_ADMIN: {
        'label': 'Администратор',
        'icon': 'bi-shield-lock',
        'css': 'role-admin',
        'description': 'Управляет пользователями и всей системой.',
        'abilities': [
            'Все возможности остальных ролей',
            'Назначение и смена ролей пользователей',
            'Доступ к админ-панели Django',
            'Полный контроль над конкурсами и проектами',
        ],
    },
}


def user_group_names(user):
    if not user.is_authenticated:
        return set()
    return set(user.groups.values_list('name', flat=True))


def has_role(user, *roles):
    """Есть ли у пользователя одна из ролей. Admin и superuser проходят всегда."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    groups = user_group_names(user)
    if ROLE_ADMIN in groups:
        return True
    return bool(groups.intersection(roles))


def is_site_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=ROLE_ADMIN).exists()
    )


def is_organizer(user):
    return has_role(user, ROLE_ORGANIZER)


def is_expert(user):
    return has_role(user, ROLE_EXPERT)


def is_mentor(user):
    return has_role(user, ROLE_MENTOR)


def is_participant(user):
    return has_role(user, ROLE_PARTICIPANT)


def primary_role(user):
    """Основная роль для отображения (приоритет от старшей к младшей)."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    groups = user_group_names(user)
    for role in [ROLE_ADMIN, ROLE_ORGANIZER, ROLE_EXPERT, ROLE_MENTOR, ROLE_PARTICIPANT]:
        if role in groups:
            return role
    return None


def set_role(user, role_name):
    """Назначает единственную роль, снимая остальные ролевые группы."""
    if role_name not in ALL_ROLES:
        raise ValueError(f'Неизвестная роль: {role_name}')
    user.groups.remove(*Group.objects.filter(name__in=ALL_ROLES))
    group, _ = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
