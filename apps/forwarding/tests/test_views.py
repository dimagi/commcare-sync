from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from tests.fixtures import admin_client, database, regular_client

from ..models import ForwardingConfig, ForwardingDestination, ForwardingRun


@fixture
@use('db')
def destination():
    yield ForwardingDestination.objects.create(
        name='Test Dest',
        api_url='https://example.com/api/',
    )


@fixture
@use('db')
def destination_in_use():
    dest = destination()
    ForwardingConfig.objects.create(
        name='Test Forwarder',
        database=database(),
        destination=dest,
        query='SELECT 1',
    )
    yield dest


@fixture
def forwarding_config():
    yield ForwardingConfig.objects.create(
        name='Test Config',
        database=database(),
        destination=destination(),
        query='SELECT 1',
    )


class TestDestinationsView:
    @use(admin_client)
    def test_admin_get_returns_200(self):
        url = reverse('forwarding:destinations')
        response = admin_client().get(url)
        assert response.status_code == 200

    def test_anonymous_redirects(self):
        url = reverse('forwarding:destinations')
        response = Client().get(url)
        assert response.status_code == 302


class TestDeleteDestinationView:
    @use(admin_client, destination)
    def test_get_with_deletable_destination_returns_200(self):
        url = reverse('forwarding:delete_destination', args=[destination().id])
        response = admin_client().get(url)
        assert response.status_code == 200

    @use(admin_client, destination)
    def test_post_with_deletable_destination_deletes_and_redirects(self):
        destination_id = destination().id
        url = reverse('forwarding:delete_destination', args=[destination_id])
        response = admin_client().post(url)
        assert response.status_code == 302
        assert reverse('forwarding:destinations') in response.url
        assert not ForwardingDestination.objects.filter(id=destination_id).exists()

    @use(admin_client, destination_in_use)
    def test_get_with_in_use_destination_redirects_with_error(self):
        url = reverse(
            'forwarding:delete_destination', args=[destination_in_use().id]
        )
        response = admin_client().get(url)
        assert response.status_code == 302
        assert reverse('forwarding:destinations') in response.url

    @use(admin_client, destination_in_use)
    def test_post_with_in_use_destination_redirects_and_does_not_delete(self):
        destination_id = destination_in_use().id
        url = reverse('forwarding:delete_destination', args=[destination_id])
        response = admin_client().post(url)
        assert response.status_code == 302
        assert reverse('forwarding:destinations') in response.url
        assert ForwardingDestination.objects.filter(id=destination_id).exists()
        messages_list = list(get_messages(response.wsgi_request))
        assert any('Cannot delete' in str(m) for m in messages_list)

    @use(regular_client, destination)
    def test_non_admin_get_redirects(self):
        url = reverse('forwarding:delete_destination', args=[destination().id])
        response = regular_client().get(url)
        assert response.status_code == 403

    @use(regular_client, destination)
    def test_non_admin_post_is_rejected(self):
        dest = destination()
        url = reverse('forwarding:delete_destination', args=[dest.pk])
        response = regular_client().post(url)
        assert response.status_code == 403
        assert ForwardingDestination.objects.filter(pk=dest.pk).exists()

    @use(destination)
    def test_anonymous_get_redirects(self):
        url = reverse('forwarding:delete_destination', args=[destination().id])
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url


@use(regular_client, forwarding_config)
class TestRunForwardingHtmxBranch:
    def test_htmx_request_returns_204(self):
        url = reverse(
            'forwarding:run_forwarding', args=[forwarding_config().id]
        )
        response = regular_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_forwarding_run(self):
        config = forwarding_config()
        url = reverse('forwarding:run_forwarding', args=[config.id])
        regular_client().post(url, HTTP_HX_REQUEST='true')
        assert ForwardingRun.objects.filter(
            forwarding_config=config,
            triggered_from_ui=True,
        ).exists()

    def test_non_htmx_request_returns_200(self):
        url = reverse(
            'forwarding:run_forwarding', args=[forwarding_config().id]
        )
        response = regular_client().post(url)
        assert response.status_code == 200
        assert len(response.content) > 0


class TestRunForwardingHtmxBranch:
    @use(regular_client, forwarding_config)
    def test_htmx_request_returns_204(self):
        url = reverse(
            'forwarding:run_forwarding', args=[forwarding_config().id]
        )
        response = regular_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    @use(regular_client, forwarding_config)
    def test_htmx_request_creates_forwarding_run(self):
        config = forwarding_config()
        url = reverse('forwarding:run_forwarding', args=[config.id])
        regular_client().post(url, HTTP_HX_REQUEST='true')
        assert ForwardingRun.objects.filter(
            forwarding_config=config,
            triggered_from_ui=True,
        ).exists()

    @use(regular_client, forwarding_config)
    def test_non_htmx_request_returns_200(self):
        url = reverse(
            'forwarding:run_forwarding', args=[forwarding_config().id]
        )
        response = regular_client().post(url)
        assert response.status_code == 200
        assert len(response.content) > 0
