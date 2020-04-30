from .settings import *
import os


DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcare_det_web',
        'USER': 'postgres',
        'PASSWORD': '*****',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


ALLOWED_HOSTS = [
    'localhost:8000',
]


# Your email config goes here.
# see https://github.com/anymail/django-anymail for more details / examples

EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'

ANYMAIL = {
    "MAILGUN_API_KEY": "key-****",
    "MAILGUN_SENDER_DOMAIN": 'localhost:8000',
}

SERVER_EMAIL = 'noreply@localhost:8000'
DEFAULT_FROM_EMAIL = 'czue+det@dimagi.com'
ADMINS = [('Your Name', 'czue+det@dimagi.com'),]

GOOGLE_ANALYTICS_ID = ''  # replace with your google analytics ID to connect to Google Analytics


# Mailchimp setup

# set these values if you want to subscribe people to a mailchimp list after they sign up.
MAILCHIMP_API_KEY = ''
MAILCHIMP_LIST_ID = ''


# Sentry setup

# populate this to configure sentry. should take the form: 'https://****@sentry.io/12345'
SENTRY_DSN = ''


if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()]
    )
