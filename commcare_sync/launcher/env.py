"""
Names shared between the launcher and the settings module.

Free of Django imports: both sides read this before ``django.setup()``.
"""

APP_NAME = 'commcare-sync'

DATA_DIR_ENV_VAR = 'COMMCARE_SYNC_DATA_DIR'

# Layout of the data directory.
LOGS_DIRNAME = 'logs'
MEDIA_DIRNAME = 'media'
