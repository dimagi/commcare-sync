from unittest.mock import Mock, patch

import pytest
from django_q.exceptions import TimeoutException
from unmagic import use

from apps.exports.models import ExportRun
from apps.exports.runner import _compile_export_command, run_export
from apps.exports.tests.fixtures import (
    export_config,
    export_config_fixture,
    export_config_db_fixture,
    project_fixture,
    project_db_fixture,
    server_fixture,
)


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
    run = ExportRun.objects.create(config=export_config())
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
    assert run.status == ExportRun.Status.STARTED
