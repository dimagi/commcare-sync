from unmagic import fixture, use

from tests.fixtures import database

from ..models import RefreshConfig, RefreshRun


@fixture
@use('db')
def refresh_config():
    yield RefreshConfig.objects.create(
        name='Test Refresh Config',
        database=database(),
        materialized_views=['public.view1', 'public.view2'],
    )


@fixture
@use('db')
def refresh_run():
    config = refresh_config()
    yield RefreshRun.objects.create(
        config=config,
        config_version=config.latest_version,
        status=RefreshRun.Status.QUEUED,
    )
