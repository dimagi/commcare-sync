from django.contrib.auth import get_user_model
from django.urls import reverse
from unmagic import fixture, use

_client = fixture('client')


@use('db', _client)
def test_login_page_renders():
    response = _client().get(reverse('login'))
    assert response.status_code == 200


@use('db', _client)
def test_password_reset_page_renders():
    response = _client().get(reverse('password_reset'))
    assert response.status_code == 200


@use('db', _client)
def test_signup_url_returns_404():
    response = _client().get('/accounts/signup/')
    assert response.status_code == 404


@use('db', _client)
def test_login_with_email():
    User = get_user_model()
    User.objects.create_user(
        email='bob@example.com', password='hunter2',
    )
    response = _client().post(
        reverse('login'),
        {'username': 'bob@example.com', 'password': 'hunter2'},
        follow=False,
    )
    assert response.status_code == 302
    assert response.url == '/'
