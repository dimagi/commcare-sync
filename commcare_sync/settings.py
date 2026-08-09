"""
Django settings for CommCare Data Pipeline
"""
import json
import os
from datetime import timedelta


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Store SECRET_KEY and FERNET_KEYS in environment variables or set them
# in commcare_sync/settings_local.py.
#
# Generate with `openssl rand -base64 48`
#SECRET_KEY = '<replace with secret key>'
#
# Generate with `./fernet-gen`
#FERNET_KEYS = [
#    '<replace with Fernet key>',
#    # Current key at the top, previous keys below
#
#]
#
# If using environment variables, store FERNET_KEYS as a JSON list, with
# the current key first, and previous keys after. e.g.
# FERNET_KEYS=`["current", "previous", "oldest"]`

if 'SECRET_KEY' in os.environ:
    SECRET_KEY = os.environ['SECRET_KEY']
if 'FERNET_KEYS' in os.environ:
    FERNET_KEYS = json.loads(os.environ['FERNET_KEYS'])  # JSON list


ALLOWED_HOSTS = []


LOG_DIR = os.path.join(BASE_DIR, 'logs')


DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.forms',
]

THIRD_PARTY_APPS = [
    'django_q',
    'reversion',
]

PROJECT_APPS = [
    'apps.commcare.apps.CommCareConfig',
    'apps.db.apps.DatabasesConfig',
    'apps.exports.apps.ExportsConfig',
    'apps.forwarding.apps.ForwardingConfig',
    'apps.refreshes.apps.RefreshesConfig',
    'apps.schedules.apps.SchedulesConfig',
    'apps.users.apps.UserConfig',
    'apps.web',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + PROJECT_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'commcare_sync.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates')
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.web.context_processors.project_meta',
                'apps.web.context_processors.google_analytics_id',
            ],
        },
    },
]

WSGI_APPLICATION = 'commcare_sync.wsgi.application'

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        'OPTIONS': {
            # WAL allows the web process and task workers to share the DB.
            'init_command': (
                'PRAGMA journal_mode=WAL;'
                'PRAGMA busy_timeout=5000;'
                'PRAGMA synchronous=NORMAL;'
            ),
            'transaction_mode': 'IMMEDIATE',
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


# Django recommends overriding the user model even if you don't think
# you need to because it makes future changes much easier.
AUTH_USER_MODEL = 'users.CustomUser'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
# Uncomment to use manifest storage to bust cache when file change
# NOTE: This may break some image references in SASS files which is why
#       it is not enabled by default.
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


# Use in development:
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# Use in production:
# see https://github.com/anymail/django-anymail for more details/examples
# EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'


# Django sites
SITE_ID = 1


# Django-Q2 task queue, brokered by the app database (ORM broker).
Q_CLUSTER = {
    'name': 'commcare_sync',
    'orm': 'default',
    'workers': 2,
    'timeout': 6 * 60 * 60,  # kill a run after 6h
    'retry': 8 * 60 * 60,  # re-deliver 2h after the timeout
    'max_attempts': 2,  # one retry for interrupted runs, then give up
    'ack_failures': True,  # a failed run is complete, not re-delivered
    'catch_up': False,  # don't replay every missed minute of the dispatcher
    'label': 'Task queue',
}


# CommCare Config

COMMCARE_DEFAULT_SERVER = 'https://www.commcarehq.org'
COMMCARE_EXPORT = 'commcare-export'  # replace with absolute path if you need

# Run everything every 12 hours by default
COMMCARE_SYNC_EXPORT_PERIODICITY = 60 * 60 * 12
COMMCARE_SYNC_UI_PAGE_SIZE = 25


PROJECT_METADATA = {
    'NAME': 'CommCare Data Pipeline',
    'URL': 'http://localhost:8001',
    'DESCRIPTION': "Continuously exports CommCare data into your own databases and BI platforms",
    'IMAGE': 'https://files.dimagi.com/wp-content/uploads/2015/11/cc23.jpg',
    'KEYWORDS': 'CommCare, Export, Data, Pipeline',
}


# This should be overridden in project-specific settings
ADMINS = [('Dimagi', 'devops+commcare-sync@dimagi.com')]


# Replace with your Google Analytics ID to connect to Google Analytics
GOOGLE_ANALYTICS_ID = ''


# Dashboard statistics period
DASHBOARD_STATS_PERIOD = timedelta(hours=24)


try:
    from .settings_local import *  # noqa
except ImportError:
    pass
