import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def admin_client(client, db):
    credentials = {'email': 'boss@example.com', 'password': 'x'}
    User.objects.create_superuser(**credentials)
    client.login(**credentials)
    return client


def test_admin_user_changelist_renders(admin_client):
    response = admin_client.get(reverse('admin:users_customuser_changelist'))
    assert response.status_code == 200
    assert b'boss@example.com' in response.content


def test_admin_user_add_page_renders(admin_client):
    response = admin_client.get(reverse('admin:users_customuser_add'))
    assert response.status_code == 200
    assert b'name="email"' in response.content
    assert b'name="password1"' in response.content
