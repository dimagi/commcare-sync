import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from unmagic import fixture, use

_client = fixture('client')


@use('db', _client)
class TestDjangoAuthURLs:

    @pytest.mark.parametrize('url,expected_code', [
        (reverse('login'), 200),  # Login page
        (reverse('password_reset'), 200),  # Password reset page
    ])
    def test_login_page_renders(self, url, expected_code):
        response = _client().get(url)
        assert response.status_code == expected_code

    def test_login_with_email(self):
        User = get_user_model()
        User.objects.create_user(
            email='bob@example.com',
            password='hunter2',
        )
        response = _client().post(
            reverse('login'),
            {'username': 'bob@example.com', 'password': 'hunter2'},
            follow=False,
        )
        assert response.status_code == 302
        assert response.url == '/'
