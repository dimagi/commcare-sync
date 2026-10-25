from importlib import import_module

from django.apps import apps
from unmagic import use

from apps.refreshes.models import RefreshRun

from .fixtures import refresh_config

rename_timeout_status = import_module(
    'apps.refreshes.migrations.0006_rename_timeout_status'
)


@use(refresh_config)
def test_timeout_rows_become_interrupted():
    run = RefreshRun.objects.create(config=refresh_config(), status='timeout')
    rename_timeout_status.forwards(apps, None)
    run.refresh_from_db()
    assert run.status == RefreshRun.Status.INTERRUPTED
