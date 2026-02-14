from apps.exports.runner import _compile_export_command
from apps.exports.tests.conftest import (
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

    command = _compile_export_command(config, project, force=False)

    assert server.url in command


@export_config_db_fixture
@project_db_fixture
def test_default_server_url():
    config = export_config_db_fixture()
    project = project_db_fixture()

    command = _compile_export_command(config, project, force=False)

    assert 'https://www.commcarehq.org' in command
