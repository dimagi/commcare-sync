from django.core.management import call_command
from unmagic import use

from apps.exports.models import ExportRun, MultiProjectExportRun
from apps.exports.tests.fixtures import export_config, multi_export_config
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.refreshes.models import RefreshRun
from apps.refreshes.tests.fixtures import refresh_config


@use(
    export_config,
    multi_export_config,
    destination,
    forwarding_config,
    refresh_config,
)
def test_clears_queued_runs_across_all_run_types():
    export_run = ExportRun.objects.create(
        config=export_config(), status=ExportRun.Status.QUEUED
    )
    multi_run = MultiProjectExportRun.objects.create(
        config=multi_export_config(),
        status=MultiProjectExportRun.Status.QUEUED,
    )
    forwarding_run = ForwardingRun.objects.create(
        config=forwarding_config(), status=ForwardingRun.Status.QUEUED
    )
    refresh_run = RefreshRun.objects.create(
        config=refresh_config(), status=RefreshRun.Status.QUEUED
    )

    call_command('clear_queued_runs')

    for run in (export_run, multi_run, forwarding_run, refresh_run):
        run.refresh_from_db()
        assert run.status == run.Status.SKIPPED
        assert run.completed_at is not None


@use(export_config)
def test_leaves_started_and_completed_runs_alone():
    config = export_config()
    started = ExportRun.objects.create(
        config=config, status=ExportRun.Status.STARTED
    )
    completed = ExportRun.objects.create(
        config=config, status=ExportRun.Status.COMPLETED
    )

    call_command('clear_queued_runs')

    started.refresh_from_db()
    completed.refresh_from_db()
    assert started.status == ExportRun.Status.STARTED
    assert completed.status == ExportRun.Status.COMPLETED
