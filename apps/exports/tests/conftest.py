import os

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import TemporaryUploadedFile
from unmagic import fixture, use

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.db.models import Database
from apps.exports.models import ExportConfig


def pytest_configure(config):
    """
    Set environment variables for Django + Playwright compatibility.

    DJANGO_ALLOW_ASYNC_UNSAFE allows Django database operations
    to run in the async context created by Playwright tests.
    """
    os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

    # Configure ALLOWED_HOSTS to accept localhost with any port
    # This is needed for pytest-django's live_server fixture which uses dynamic ports
    settings.ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver', '.localhost']

    # Disable allauth rate limiting for tests
    settings.ACCOUNT_RATE_LIMITS = {
        'login_failed': None,
        'login': None,
        'signup': None,
    }


@pytest.fixture(scope='session')
def browser_context_args(browser_context_args):
    """
    Configure browser context for all Playwright tests.
    """
    return {
        **browser_context_args,
        'viewport': {
            'width': 1280,
            'height': 720,
        },
        'locale': 'en-US',
        'timezone_id': 'America/New_York',
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
def user_fixture():
    User = get_user_model()
    yield User.objects.create(
        username='test_user',
        email='test@example.com',
        password='P@ssWord',
    )


@use("db")
@fixture
def server_db_fixture():
    from django.conf import settings

    server, _ = CommCareServer.objects.get_or_create(
        url=settings.COMMCARE_DEFAULT_SERVER
    )
    yield server


@fixture
def project_db_fixture():
    server = server_db_fixture()
    yield CommCareProject.objects.create(server=server, domain='foo')


@fixture
def account_db_fixture():
    server = server_db_fixture()
    user = user_fixture()
    yield CommCareAccount.objects.create(
        server=server,
        username='foo',
        api_key='P@ssWord',
        owner=user,
    )


@fixture
def database_db_fixture():
    user = user_fixture()
    yield Database.objects.create(
        name='Test DB',
        connection_string='postgresql://foo:bar@123.4.0.0/test',
        owner=user,
    )


@fixture
def export_config_db_fixture():
    project = project_db_fixture()
    account = account_db_fixture()
    database = database_db_fixture()
    user = user_fixture()
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
        database=database,
        config_file=config_file,
        extra_args='',
        created_by=user,
    )
    config_file.close()
    yield export_config
