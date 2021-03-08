from .settings import *

# just an example of using .env.dev to pass data to settings
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)
REDIS_URL = 'redis://redis:6379'  # from docker compose file
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcare_sync',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'db',  # from docker compose file
        'PORT': '5432',
    }
}
