from django.test import SimpleTestCase
from django.core.files.uploadedfile import TemporaryUploadedFile

from apps.commcare.models import CommCareServer, CommCareProject, CommCareAccount

from apps.exports.models import ExportConfig, ExportDatabase


class BaseSimpleExportTestCase(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = CommCareServer(name="Test Server", url="https://www.example.com")
        cls.project = CommCareProject(server=cls.server, domain="foo")
        cls.account = CommCareAccount(server=cls.server, username="foo", api_key="P@ssWord")
        cls.database = ExportDatabase(
            name="Test DB", connection_string="postgresql://foo:bar@123.4.0.0/test"
        )
        cls.config_file = TemporaryUploadedFile(
            name="config_file", content_type="application/xml", size=100, charset="utf-8"
        )
        cls.export_config = ExportConfig(
            name="Test Config",
            project=cls.project,
            account=cls.account,
            database=cls.database,
            config_file=cls.config_file,
            extra_args="",
        )
