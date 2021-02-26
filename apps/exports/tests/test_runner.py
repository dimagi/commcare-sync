from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.exports.models import ExportConfig, ExportDatabase
from apps.exports.runner import _compile_export_command
from apps.exports.tests.test_utils import BaseSimpleExportTestCase
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import TestCase


class TestRunnerArguments(BaseSimpleExportTestCase):

    def test_custom_server_url(self):
        command = _compile_export_command(self.export_config, self.project, force=False)

        self.assertIn(self.server.url, command)


class RunnerArgumentsDbTest(TestCase):

    def test_default_server_url(self):
        server = CommCareServer.objects.get()
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

        self.assertIn('https://www.commcarehq.org', command)
