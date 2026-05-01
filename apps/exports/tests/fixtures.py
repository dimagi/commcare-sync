"""
Shared test fixtures for export tests.
"""
from django.contrib.auth import get_user_model
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.db.models import Database

User = get_user_model()


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

    database = Database.objects.create(
        name='Test Database',
        connection_string='postgresql://testuser:password@localhost:5432/testdb',
    )

    yield {
        'user': user,
        'server': server,
        'account': account,
        'project': project,
        'database': database,
    }
