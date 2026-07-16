"""Shared test fixtures available across the project.

Imported explicitly by tests, e.g.:

    from tests.fixtures import user, commcare_server

    @use(user)
    def test_something():
        ...
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client
from unmagic import fixture, use

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.db.models import Database


@fixture
@use('db')
def user():
    User = get_user_model()
    yield User.objects.create_user(
        email='test@example.com',
        password='testpass',
    )


@fixture
@use('db')
def regular_user():
    User = get_user_model()
    yield User.objects.create_user(
        email='regular@example.com',
        password='pass',
    )


@fixture
@use('db')
def admin_user():
    User = get_user_model()
    yield User.objects.create_user(
        email='admin@example.com',
        password='pass',
        is_active=True,
        is_superuser=True,
        is_staff=True,
    )


@fixture
@use('db')
def regular_client():
    client = Client()
    client.force_login(regular_user())
    yield client


@fixture
@use('db')
def admin_client():
    client = Client()
    client.force_login(admin_user())
    yield client


@fixture
@use('db')
def authed_client():
    client = Client()
    client.force_login(user())
    yield client


@fixture
@use('db')
def htmx_client():
    # Sends the HX-Request header that HTMX adds to every request, for use
    # against endpoints that only accept HTMX requests (see require_htmx).
    client = Client(headers={'HX-Request': 'true'})
    client.force_login(user())
    yield client


@fixture
@use('db')
def commcare_server():
    yield CommCareServer.objects.create(
        name='Test Server',
        url='https://test.commcarehq.org',
    )


@fixture
@use('db')
def commcare_account():
    yield CommCareAccount.objects.create(
        username='test@dimagi.com',
        api_key='test-api-key-12345',
        server=commcare_server(),
        owner=user(),
    )


@fixture
@use('db')
def commcare_project():
    yield CommCareProject.objects.create(
        domain='test-domain',
        server=commcare_server(),
    )


@fixture
@use('db')
def database():
    yield Database.objects.create(
        name='Test Database',
        connection_string='postgresql://testuser:password@localhost:5432/testdb',
    )


@fixture
def mock_celery_task_dispatch():
    # Prevent Celery from connecting to Redis when dispatching tasks.
    with patch(
        'celery.app.task.Task.apply_async',
        return_value=MagicMock(id='test-task-id', task_id='test-task-id'),
    ):
        yield
