from django.test import SimpleTestCase

from django.core.files.uploadedfile import TemporaryUploadedFile
from apps.commcare.models import CommCareServer, CommCareProject, CommCareAccount

from apps.exports.models import ExportConfig, ExportDatabase

from apps.exports.runner import _compile_export_command


class TestRunnerArguments(SimpleTestCase):
    def test_custom_server_url(self):
        server = CommCareServer(name="Test Server", url="https://www.example.com")
        project = CommCareProject(server=server, domain="foo")
        account = CommCareAccount(server=server, username="foo", api_key="P@ssWord")
        database = ExportDatabase(
            name="Test DB", connection_string="postgresql://foo:bar@123.4.0.0/test"
        )
        config_file = TemporaryUploadedFile(
            name="config_file", content_type="application/xml", size=100, charset="utf-8"
        )
        export_config = ExportConfig(
            name="Test Config",
            project=project,
            account=account,
            database=database,
            config_file=config_file,
            extra_args="",
        )

        command = _compile_export_command(export_config, project, force=False)

        self.assertIn(server.url, command)
