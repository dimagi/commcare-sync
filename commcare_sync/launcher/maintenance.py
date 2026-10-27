"""
Startup maintenance for the launcher, between ``migrate`` and starting
the cluster: repairs what a previous process left behind, and creates
the admin user named in the environment, if any.

Imports Django models, so it must be imported after ``django.setup()``.
"""

import logging
import os

from apps.schedules.maintenance import (
    clear_stale_queue_locks,
    ensure_dispatcher_schedule,
)
from apps.schedules.tasks import interrupt_unfinished_runs
from apps.users.setup import (
    ADMIN_EMAIL_VAR,
    ADMIN_PASSWORD_VAR,
    provision_admin,
)

# The launcher's logger: the app's logging drops anything below WARNING.
logger = logging.getLogger(__name__)


def repair_task_queue() -> None:
    """
    Runs before the cluster starts, when no run can be in progress. That
    holds only because nothing else runs a cluster against the same
    database: a developer running ``manage.py qcluster`` with
    ``COMMCARE_SYNC_DATA_DIR`` pointing at a launcher's data directory
    would have their runs interrupted at the next launch.

    Interrupting before clearing locks means every task delivered again
    finds its run INTERRUPTED, so ``claim_run`` retries it once.
    """
    if ensure_dispatcher_schedule():
        logger.info('Recreated the dispatcher schedule')
    interrupted = interrupt_unfinished_runs()
    if interrupted:
        logger.info('Marked %s unfinished run(s) as interrupted', interrupted)
    cleared = clear_stale_queue_locks()
    if cleared:
        logger.info('Made %s abandoned task(s) deliverable again', cleared)


def create_admin_from_environment() -> None:
    # Popped so that the cluster child, and every commcare-export it
    # starts, do not inherit them. This process's own initial environment
    # (/proc/<pid>/environ on Linux) still shows them, as it would for
    # any program handed a password this way.
    email = os.environ.pop(ADMIN_EMAIL_VAR, None)
    password = os.environ.pop(ADMIN_PASSWORD_VAR, None)
    if provision_admin(email, password):
        logger.info('Created the admin user named by %s', ADMIN_EMAIL_VAR)
