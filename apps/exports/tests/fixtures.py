"""
Shared test fixtures for export tests.
"""
from django.core.files.uploadedfile import TemporaryUploadedFile
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.db.models import Database
from apps.exports.models import ExportConfig
from tests.fixtures import (
    commcare_account,
    commcare_project,
    commcare_server,
    database,
    user,
)


@fixture
@use('db')
def test_data():
    """Create all test data needed for export form tests."""
    yield {
        'user': user(),
        'server': commcare_server(),
        'account': commcare_account(),
        'project': commcare_project(),
        'database': database(),
    }


@fixture
def server_fixture():
    yield CommCareServer(name='Test Server', url='https://www.example.com')


@fixture
def project_fixture():
    server = server_fixture()
    yield CommCareProject(server=server, domain='foo')


@fixture
def account_fixture():
    server = server_fixture()
    yield CommCareAccount(server=server, username='foo', api_key='P@ssWord')


@fixture
def database_fixture():
    yield Database(
        name='Test DB',
        connection_string='postgresql://foo:bar@123.4.0.0/test',
    )


@fixture
def config_file_fixture():
    yield TemporaryUploadedFile(
        name='config_file',
        content_type='application/xml',
        size=100,
        charset='utf-8',
    )


@fixture
def export_config_fixture():
    project = project_fixture()
    account = account_fixture()
    database = database_fixture()
    config_file = config_file_fixture()
    yield ExportConfig(
        name='Test Config',
        project=project,
        account=account,
        database=database,
        config_file=config_file,
        extra_args='',
    )


@use("db")
@fixture
def server_db_fixture():
    from django.conf import settings

    server, _ = CommCareServer.objects.get_or_create(
        url=settings.COMMCARE_DEFAULT_SERVER
    )
    yield server


@use("db")
@fixture
def project_db_fixture():
    server = server_db_fixture()
    yield CommCareProject.objects.create(server=server, domain='foo')


@use("db")
@fixture
def account_db_fixture():
    server = server_db_fixture()
    yield CommCareAccount.objects.create(
        server=server,
        username='foo',
        api_key='P@ssWord',
        owner=user(),
    )


@use("db")
@fixture
def export_config_db_fixture():
    project = project_db_fixture()
    account = account_db_fixture()
    config_file = TemporaryUploadedFile(
        name='config_file',
        content_type='application/xml',
        size=100,
        charset='utf-8',
    )
    export_config = ExportConfig.objects.create(
        name='Test Config',
        project=project,
        account=account,
        database=database(),
        config_file=config_file,
        extra_args='',
    )
    config_file.close()
    yield export_config


@fixture
@use('db')
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export Config',
        project=commcare_project(),
        account=commcare_account(),
        database=database(),
    )
