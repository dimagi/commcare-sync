from .settings import *  # noqa: F403

REDIS_URL = 'redis://redis:6379'  # internal Docker network port
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcare_sync',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'db',  # from docker compose file
        'PORT': '5432',  # internal Docker network port
    }
}
