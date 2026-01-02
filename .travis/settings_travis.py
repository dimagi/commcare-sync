from .settings import *  # noqa

SECRET_KEY = 'it(5855w8z-6)9%&71n=u!upv1q7sl^xh!iisymue9v5xk36an'
FERNET_KEYS = ['sGylGjTyNm64l4-F448DiMjS6cE1qZ9b5UZWPxTu2po=']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcare_sync_test',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}
