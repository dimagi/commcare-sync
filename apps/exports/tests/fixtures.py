"""
Shared test fixtures for export tests.
"""
from django.contrib.auth import get_user_model
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.exports.models import ExportDatabase

User = get_user_model()


@fixture
@use('db')
def test_user():
    """Create a test user for authenticated requests."""
    yield User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@fixture
@use('db')
def commcare_server():
    """Create a CommCare server instance."""
    yield CommCareServer.objects.create(
        name='Test Server',
        url='https://test.commcarehq.org'
    )


@fixture
@use('db')
def commcare_account():
    """Create a CommCare account."""
    user = test_user()
    server = commcare_server()
    yield CommCareAccount.objects.create(
        username='test@dimagi.com',
        api_key='test-api-key-12345',
        server=server,
        owner=user
    )


@fixture
@use('db')
def commcare_project():
    """Create a CommCare project."""
    server = commcare_server()
    yield CommCareProject.objects.create(
        domain='test-domain',
        server=server
    )


@fixture
@use('db')
def export_database():
    """Create an export database."""
    user = test_user()
    yield ExportDatabase.objects.create(
        name='Test Database',
        connection_string='postgresql://testuser:password@localhost:5432/testdb',
        owner=user
    )


@fixture
@use('db')
def test_data():
    """Create all test data needed for export form tests."""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

    server = CommCareServer.objects.create(
        name='Test Server',
        url='https://test.commcarehq.org'
    )

    account = CommCareAccount.objects.create(
        username='test@dimagi.com',
        api_key='test-api-key-12345',
        server=server,
        owner=user
    )

    project = CommCareProject.objects.create(
        domain='test-domain',
        server=server
    )

    database = ExportDatabase.objects.create(
        name='Test Database',
        connection_string='postgresql://testuser:password@localhost:5432/testdb',
        owner=user
    )

    yield {
        'user': user,
        'server': server,
        'account': account,
        'project': project,
        'database': database,
    }
