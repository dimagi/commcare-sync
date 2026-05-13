"""Shared test fixtures available across the project.

Imported explicitly by tests, e.g.:

    from tests.fixtures import user, commcare_server

    @use(user)
    def test_something():
        ...
"""
from django.contrib.auth import get_user_model
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
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
