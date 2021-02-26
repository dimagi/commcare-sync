from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.exports.models import ExportConfig, ExportDatabase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import SimpleTestCase, TestCase


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


class BaseExportTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = get_user_model().objects.create(username="test_user", email="P@ssWord")
        cls.server = CommCareServer.objects.get()
        cls.project = CommCareProject.objects.create(server=cls.server, domain="foo")
        cls.account = CommCareAccount.objects.create(
            server=cls.server, username="foo", api_key="P@ssWord", owner=cls.user
        )
        cls.database = ExportDatabase.objects.create(
            name="Test DB",
            connection_string="postgresql://foo:bar@123.4.0.0/test",
            owner=cls.user,
        )
        config_file = TemporaryUploadedFile(
            name="config_file", content_type="application/xml", size=100, charset="utf-8"
        )
        cls.export_config = ExportConfig.objects.create(
            name="Test Config",
            project=cls.project,
            account=cls.account,
            database=cls.database,
            config_file=config_file,
            extra_args="",
            created_by=cls.user,
        )
        config_file.close()

    @classmethod
    def tearDownClass(cls):
        cls.export_config.delete()
        cls.database.delete()
        cls.account.delete()
        cls.project.delete()
        cls.user.delete()
        super().tearDownClass()
