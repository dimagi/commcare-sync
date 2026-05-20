from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from tests.fixtures import user


@fixture
@use(user)
def regular_client():
    client = Client()
    client.force_login(user())
    yield client


class TestProjectsView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('commcare:projects')
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client)
    def test_logged_in_user_gets_200(self):
        url = reverse('commcare:projects')
        response = regular_client().get(url)
        assert response.status_code == 200
