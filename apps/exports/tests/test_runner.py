from unittest.mock import Mock, patch

import pytest
from django_q.exceptions import TimeoutException
from unmagic import use

from apps.exports.models import (
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)
from apps.exports.runner import (
    _compile_export_command,
    run_export,
    run_multi_project_export,
)
from apps.exports.tests.fixtures import (
    export_config,
    multi_export_config,
    export_config_fixture,
    export_config_db_fixture,
    project_fixture,
    project_db_fixture,
    server_fixture,
)
from tests.fixtures import commcare_project


@export_config_fixture
@project_fixture
@server_fixture
def test_custom_server_url():
    config = export_config_fixture()
    project = project_fixture()
    server = server_fixture()

    command = _compile_export_command(config, project, start_over=False)

    assert server.url in command


@export_config_db_fixture
@project_db_fixture
def test_default_server_url():
    config = export_config_db_fixture()
    project = project_db_fixture()

    command = _compile_export_command(config, project, start_over=False)

    assert 'https://www.commcarehq.org' in command


@use(export_config)
def test_a_timeout_kills_commcare_export():
    # Django Q2's timeout raises TimeoutException, a SystemExit, while the
    # log is streaming. The child process must not outlive the worker.
    run = ExportRun.objects.create(
        config=export_config(), status=ExportRun.Status.STARTED
    )
    process = Mock()
    process.poll.return_value = None

    with (
        patch('apps.exports.runner._compile_export_command', return_value=[]),
        patch('apps.exports.runner.subprocess.Popen', return_value=process),
        patch(
            'apps.exports.runner._stream_log',
            side_effect=TimeoutException('Task exceeded maximum timeout'),
        ),
        pytest.raises(TimeoutException),
    ):
        run_export(run)

    process.kill.assert_called_once()
    run.refresh_from_db()
    # Left STARTED for reap_stale_runs to mark TIMEOUT.
    assert run.status == ExportRun.Status.STARTED


@use(multi_export_config, commcare_project)
def test_partial_runs_are_created_started():
    # Nothing claims a partial run, so the runner starts it, which gives
    # reap_stale_runs a started_at to measure from.
    multi_config = multi_export_config()
    multi_config.projects.add(commcare_project())
    parent = MultiProjectExportRun.objects.create(
        config=multi_config, status=MultiProjectExportRun.Status.STARTED
    )
    seen = []

    def record_state(export_config, project, export_record, start_over):
        seen.append((export_record.status, export_record.started_at))
        return export_record

    with patch(
        'apps.exports.runner._run_export_for_project', side_effect=record_state
    ):
        run_multi_project_export(parent)

    [(status, started_at)] = seen
    assert status == MultiProjectPartialExportRun.Status.STARTED
    assert started_at is not None
