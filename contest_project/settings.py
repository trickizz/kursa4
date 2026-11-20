from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-change-me-in-production'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'contests',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
            ],
        },
    },
]

# Тема админ-панели Jazzmin подключается, если пакет установлен (см. requirements.txt)
try:
    import jazzmin  # noqa: F401
    INSTALLED_APPS.insert(0, 'jazzmin')
except ImportError:
    pass

WSGI_APPLICATION = 'contest_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

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
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# error -> bootstrap danger
from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {message_constants.ERROR: 'danger'}

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

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
        "contests.Contest": "fas fa-trophy",
        "contests.Stage": "fas fa-list-ol",
        "contests.Project": "fas fa-rocket",
        "contests.Criterion": "fas fa-check-double",
        "contests.Evaluation": "fas fa-star",
        "contests.Comment": "fas fa-comments",
        "contests.Document": "fas fa-file-alt",
        "contests.ProjectVote": "fas fa-heart",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar": "navbar-indigo navbar-dark",
    "sidebar": "sidebar-dark-indigo",
    "accent": "accent-indigo",
    "brand_colour": "navbar-indigo",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
    },
}