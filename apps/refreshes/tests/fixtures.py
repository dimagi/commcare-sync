import pytest
from django.contrib.auth import get_user_model

from apps.db.models import Database

from ..models import RefreshConfig, RefreshRun

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser', email='test@example.com', password='testpass'
    )


@pytest.fixture
def database(db):
    return Database.objects.create(
        name='Test PostgreSQL',
        connection_string='postgresql://localhost/test',
    )


@pytest.fixture
def refresh_config(db, database):
    return RefreshConfig.objects.create(
        name='Test Refresh Config',
        database=database,
        materialized_views=['public.view1', 'public.view2'],
    )


@pytest.fixture
def refresh_run(db, refresh_config):
    return RefreshRun.objects.create(
        refresh_config=refresh_config,
        refresh_config_version=refresh_config.latest_version,
        status=RefreshRun.Status.QUEUED,
    )
