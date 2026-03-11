from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

User = get_user_model()


@fixture
@use('db')
def user():
    yield User.objects.create_user(
        username='fwdviewuser', email='fwd@example.com', password='pass'
    )


@fixture
def authed_client():
    client = Client()
    client.force_login(user())
    yield client


class TestForwardersListView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        response = client.get(reverse('forwarding:forwarders'))
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(authed_client)
    def test_stats_in_context(self):
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context
