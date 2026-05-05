import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse('login'))
    assert response.status_code == 200


@pytest.mark.django_db
def test_password_reset_page_renders(client):
    response = client.get(reverse('password_reset'))
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_url_returns_404(client):
    response = client.get('/accounts/signup/')
    assert response.status_code == 404


@pytest.mark.django_db
def test_login_with_email(client):
    User = get_user_model()
    User.objects.create_user(
        username='bob', email='bob@example.com', password='hunter2',
    )
    response = client.post(
        reverse('login'),
        {'username': 'bob@example.com', 'password': 'hunter2'},
        follow=False,
    )
    assert response.status_code == 302
    assert response.url == '/'
