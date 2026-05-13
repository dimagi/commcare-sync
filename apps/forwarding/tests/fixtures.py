from unmagic import fixture, use

from tests.fixtures import database

from ..models import ForwardingConfig, ForwardingDestination


@fixture
@use('db')
def destination():
    yield ForwardingDestination.objects.create(
        name='Test API',
        api_url='https://example.com/api',
    )


@fixture
@use('db')
def forwarding_config():
    yield ForwardingConfig.objects.create(
        name='Test Forwarder',
        database=database(),
        destination=destination(),
        query='SELECT 1',
    )
