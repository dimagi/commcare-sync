from apps.exports.runner import _compile_export_command
from apps.exports.tests.test_utils import BaseSimpleExportTestCase, BaseExportTestCase


class TestRunnerArguments(BaseSimpleExportTestCase):

    def test_custom_server_url(self):
        command = _compile_export_command(self.export_config, self.project, force=False)

        assert self.server.url in command


class RunnerArgumentsDbTest(BaseExportTestCase):

    def test_default_server_url(self):
        command = _compile_export_command(self.export_config, self.project, force=False)

        assert 'https://www.commcarehq.org' in command
