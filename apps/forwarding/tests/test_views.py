import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='fwdviewuser', email='fwd@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


class TestForwardersListView:
    def test_requires_login(self, client, user):
        client.logout()
        url = reverse('forwarding:forwarders')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_stats_in_context(self, client, db):
        url = reverse('forwarding:forwarders')
        response = client.get(url)
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context
