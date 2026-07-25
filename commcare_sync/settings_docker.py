from .settings import *  # noqa: F403

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
