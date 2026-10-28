"""
Names shared between the launcher and the settings module.

Free of Django imports: both sides read this before ``django.setup()``.
"""

import sys
from enum import StrEnum

APP_NAME = 'commcare-sync'

DATA_DIR_ENV_VAR = 'COMMCARE_SYNC_DATA_DIR'
MODE_ENV_VAR = 'COMMCARE_SYNC_MODE'
PORT_ENV_VAR = 'COMMCARE_SYNC_PORT'
ALLOWED_HOSTS_ENV_VAR = 'COMMCARE_SYNC_ALLOWED_HOSTS'
BEHIND_PROXY_ENV_VAR = 'COMMCARE_SYNC_BEHIND_PROXY'
SETUP_TOKEN_ENV_VAR = 'COMMCARE_SYNC_SETUP_TOKEN'

# Layout of the data directory.
LOGS_DIRNAME = 'logs'
MEDIA_DIRNAME = 'media'
STATIC_ROOT_DIRNAME = 'static_root'
DATABASE_FILENAME = 'db.sqlite3'
APP_LOG_FILENAME = 'app.log'
LAUNCHER_LOG_FILENAME = 'launcher.log'
OPEN_PAGE_FILENAME = 'open.html'

LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'


class Mode(StrEnum):
    DESKTOP = 'desktop'
    SERVER = 'server'


# A PyInstaller bundle has no commcare-export script and no system
# Python, so it runs the export tool itself: apps.exports.runner starts
# sys.executable with RUN_DET_FLAG, and launcher.cli hands the rest of
# the arguments to the tool.
RUN_DET_FLAG = '--run-det'


def is_frozen() -> bool:
    return getattr(sys, 'frozen', False)
