from importlib import import_module

from django.apps import apps
from unmagic import use

from apps.exports.models import ExportRun, MultiProjectExportRun

from .fixtures import export_config, multi_export_config

rename_timeout_status = import_module(
    'apps.exports.migrations.0030_rename_timeout_status'
)


@use(export_config, multi_export_config)
def test_timeout_rows_become_interrupted_in_every_run_model():
    run = ExportRun.objects.create(config=export_config(), status='timeout')
    multi_run = MultiProjectExportRun.objects.create(
        config=multi_export_config(), status='timeout'
    )
    rename_timeout_status.forwards(apps, None)
    run.refresh_from_db()
    multi_run.refresh_from_db()
    assert run.status == ExportRun.Status.INTERRUPTED
    assert multi_run.status == MultiProjectExportRun.Status.INTERRUPTED
