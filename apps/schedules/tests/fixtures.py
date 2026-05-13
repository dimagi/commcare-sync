from unmagic import fixture, use

from apps.forwarding.models import ForwardingDestination


@fixture
@use('db')
def destination():
    yield ForwardingDestination.objects.create(
        name='Test API',
        api_url='https://example.com/api',
    )
