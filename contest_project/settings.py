from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-dev-key-change-me'),
    ALLOWED_HOSTS=(list, ['*']),
    RATELIMIT_ENABLE=(bool, True),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'contests',
]

# Тема админ-панели Jazzmin подключается, если пакет установлен (см. requirements.txt).
# В режиме тестов отключается (несовместимость jazzmin с coverage-трассировкой).
import sys as _sys
_TESTING = 'test' in _sys.argv
try:
    if not _TESTING:
        import jazzmin  # noqa: F401
        INSTALLED_APPS.insert(0, 'jazzmin')
except ImportError:
    pass

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'contest_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'contests' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'contests.context_processors.roles',
                'contests.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'contest_project.wsgi.application'

# БД из .env (sqlite по умолчанию, postgres для docker-compose)
DATABASES = {'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {message_constants.ERROR: 'danger'}

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Почта: в разработке письма (в т.ч. сброс пароля) печатаются в консоль
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = 'noreply@contest-project.local'

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

# Лимиты частоты AJAX-действий (голоса/комментарии)
RATELIMIT_ENABLE = env('RATELIMIT_ENABLE')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Конкурс проектов — API',
    'DESCRIPTION': 'REST API платформы конкурсов: конкурсы, проекты, оценки, голосование.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

JAZZMIN_SETTINGS = {
    "site_title": "Панель управления",
    "site_header": "Панель управления",
    "site_brand": "🏆 Конкурсы проектов",
    "welcome_sign": "Добро пожаловать в панель управления",
    "copyright": "Курсовой проект, 2026",
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-user-tag",
        "authtoken.tokenproxy": "fas fa-key",
        "contests.Contest": "fas fa-trophy",
        "contests.Stage": "fas fa-list-ol",
        "contests.Project": "fas fa-rocket",
        "contests.Criterion": "fas fa-check-double",
        "contests.Evaluation": "fas fa-star",
        "contests.Comment": "fas fa-comments",
        "contests.Document": "fas fa-file-alt",
        "contests.ProjectVote": "fas fa-heart",
        "contests.Notification": "fas fa-bell",
        "contests.StatusChange": "fas fa-history",
        "contests.ExpertAssignment": "fas fa-user-check",
        "contests.TeamInvite": "fas fa-user-plus",
        "contests.Achievement": "fas fa-medal",
        "contests.UserAchievement": "fas fa-award",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar": "navbar-indigo navbar-dark",
    "sidebar": "sidebar-dark-indigo",
    "accent": "accent-indigo",
    "brand_colour": "navbar-indigo",
    "button_classes": {"primary": "btn-primary", "secondary": "btn-secondary"},
}
