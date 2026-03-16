import pytest
from django.contrib.auth import get_user_model

from apps.db.models import Database
from apps.forwarding.models import ForwardingDestination

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser', email='test@example.com', password='testpass'
    )


@pytest.fixture
def database(user):
    return Database.objects.create(
        name='Test DB',
        connection_string='postgresql://localhost/test',
        owner=user,
    )


@pytest.fixture
def destination(user):
    return ForwardingDestination.objects.create(
        name='Test API',
        api_url='https://example.com/api',
        owner=user,
    )
