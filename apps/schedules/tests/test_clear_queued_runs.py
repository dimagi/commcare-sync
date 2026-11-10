from io import StringIO

from django.core.management import call_command
from unmagic import use

from apps.exports.models import (
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)
from apps.exports.tests.fixtures import export_config, multi_export_config
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.refreshes.models import RefreshRun
from apps.refreshes.tests.fixtures import refresh_config
from tests.fixtures import commcare_project


@use(
    export_config,
    multi_export_config,
    destination,
    forwarding_config,
    refresh_config,
    commcare_project,
)
def test_clears_queued_runs_across_all_run_types():
    export_run = ExportRun.objects.create(
        config=export_config(), status=ExportRun.Status.QUEUED
    )
    multi_run = MultiProjectExportRun.objects.create(
        config=multi_export_config(),
        status=MultiProjectExportRun.Status.QUEUED,
    )
    partial_run = MultiProjectPartialExportRun.objects.create(
        parent_run=multi_run,
        project=commcare_project(),
        status=MultiProjectPartialExportRun.Status.QUEUED,
    )
    forwarding_run = ForwardingRun.objects.create(
        config=forwarding_config(), status=ForwardingRun.Status.QUEUED
    )
    refresh_run = RefreshRun.objects.create(
        config=refresh_config(), status=RefreshRun.Status.QUEUED
    )

    out = StringIO()
    call_command('clear_queued_runs', stdout=out)

    for run in (
        export_run, multi_run, partial_run, forwarding_run, refresh_run
    ):
        run.refresh_from_db()
        assert run.status == run.Status.SKIPPED
        assert run.completed_at is not None
    assert out.getvalue().splitlines() == [
        'Export runs: 1 skipped',
        'Multi project export runs: 1 skipped',
        'Multi project partial export runs: 1 skipped',
        'Forwarding runs: 1 skipped',
        'Refresh runs: 1 skipped',
    ]


@use(export_config)
def test_leaves_started_and_completed_runs_alone():
    config = export_config()
    started = ExportRun.objects.create(
        config=config, status=ExportRun.Status.STARTED
    )
    completed = ExportRun.objects.create(
        config=config, status=ExportRun.Status.COMPLETED
    )

    out = StringIO()
    call_command('clear_queued_runs', stdout=out)

    started.refresh_from_db()
    completed.refresh_from_db()
    assert started.status == ExportRun.Status.STARTED
    assert completed.status == ExportRun.Status.COMPLETED
    assert out.getvalue() == 'No queued runs to skip\n'
