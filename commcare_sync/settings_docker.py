from .settings import *  # noqa: F403

REDIS_URL = 'redis://redis:6380'  # from docker compose file
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcare_sync',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'db',  # from docker compose file
        'PORT': '5433',
    }
}

# enable public sign-ups
ACCOUNT_ADAPTER = 'apps.users.account_adapter.EmailAsUsernameAdapter'
