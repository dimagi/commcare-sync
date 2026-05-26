"""Shared test fixtures available across the project.

Imported explicitly by tests, e.g.:

    from tests.fixtures import user, commcare_server

    @use(user)
    def test_something():
        ...
"""
from django.contrib.auth import get_user_model
from django.test import Client
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.db.models import Database


@fixture
@use('db')
def user():
    User = get_user_model()
    yield User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass',
    )


@fixture
@use('db')
def regular_user():
    User = get_user_model()
    yield User.objects.create_user(
        username='regularuser',
        email='regular@example.com',
        password='pass',
    )


@fixture
@use('db')
def admin_user():
    User = get_user_model()
    yield User.objects.create_user(
        username='adminuser',
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
