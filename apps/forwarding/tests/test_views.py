from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.db.models import Database

from ..models import ForwardingConfig, ForwardingDestination, ForwardingRun

User = get_user_model()


@fixture
@use('db')
def admin_user():
    yield User.objects.create_user(
        username='fwdadminuser',
        email='fwdadmin@example.com',
        password='testpass',
        is_active=True,
        is_superuser=True,
        is_staff=True,
    )


@fixture
@use('db')
def regular_user():
    yield User.objects.create_user(
        username='fwdregularuser',
        email='fwdregular@example.com',
        password='testpass',
    )


@fixture
def admin_client():
    client = Client()
    client.force_login(admin_user())
    yield client


@fixture
def regular_client():
    client = Client()
    client.force_login(regular_user())
    yield client


@fixture
@use('db')
def destination():
    yield ForwardingDestination.objects.create(
        name='Test Dest',
        api_url='https://example.com/api/',
    )


@fixture
@use('db')
def database():
    db_obj = Database(name='Test DB')
    db_obj.connection_string = 'postgresql://localhost/testdb'
    db_obj.save()
    yield db_obj


@fixture
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


class TestForwardingRunButtonRendering:
    @use(regular_client, forwarding_config)
    def test_run_button_present_when_no_active_run(self):
        config = forwarding_config()
        url = reverse('forwarding:config_table')
        response = regular_client().get(url)
        assert response.status_code == 200
        content = response.content.decode()
        run_url = reverse('forwarding:run_forwarding', args=[config.id])
        assert f'hx-post="{run_url}"' in content

    @use(regular_client, forwarding_config)
    def test_run_button_disabled_when_active_run(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.QUEUED,
        )
        url = reverse('forwarding:config_table')
        response = regular_client().get(url)
        content = response.content.decode()
        assert 'btn-outline-success' in content
        run_url = reverse('forwarding:run_forwarding', args=[config.id])
        assert f'hx-post="{run_url}"' not in content

    @use(regular_client, forwarding_config)
    def test_edit_button_never_disabled(self):
        config = forwarding_config()
        url = reverse('forwarding:config_table')
        response = regular_client().get(url)
        content = response.content.decode()
        edit_url = reverse(
            'forwarding:edit_forwarding_config', args=[config.id]
        )
        assert edit_url in content
