import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from ..models import ForwardingConfig, ForwardingDestination, ForwardingRun

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='fwdadminuser',
        email='fwdadmin@example.com',
        password='pass',
        is_active=True,
        is_superuser=True,
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username='fwdregularuser',
        email='fwdregular@example.com',
        password='pass',
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def regular_client(client, regular_user):
    client.force_login(regular_user)
    return client


@pytest.fixture
def destination(db):
    return ForwardingDestination.objects.create(
        name='Test Dest',
        api_url='https://example.com/api/',
    )


@pytest.fixture
def database(db):
    from apps.db.models import Database

    db_obj = Database(name='Test DB')
    db_obj.connection_string = 'postgresql://localhost/testdb'
    db_obj.save()
    return db_obj


@pytest.fixture
def destination_in_use(db, destination, database):
    ForwardingConfig.objects.create(
        name='Test Forwarder',
        database=database,
        destination=destination,
        query='SELECT 1',
    )
    return destination


@pytest.mark.django_db
class TestDestinationsView:
    def test_admin_get_returns_200(self, admin_client):
        url = reverse('forwarding:destinations')
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_anonymous_redirects(self, client):
        url = reverse('forwarding:destinations')
        response = client.get(url)
        assert response.status_code == 302


@pytest.mark.django_db
class TestDeleteDestinationView:
    def test_get_with_deletable_destination_returns_200(
        self, admin_client, destination
    ):
        url = reverse('forwarding:delete_destination', args=[destination.id])
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_post_with_deletable_destination_deletes_and_redirects(
        self, admin_client, destination
    ):
        destination_id = destination.id
        url = reverse('forwarding:delete_destination', args=[destination_id])
        response = admin_client.post(url)
        assert response.status_code == 302
        assert reverse('forwarding:destinations') in response.url
        assert not ForwardingDestination.objects.filter(id=destination_id).exists()

    def test_get_with_in_use_destination_redirects_with_error(
        self, admin_client, destination_in_use
    ):
        url = reverse(
            'forwarding:delete_destination', args=[destination_in_use.id]
        )
        response = admin_client.get(url)
        assert response.status_code == 302
        assert reverse('forwarding:destinations') in response.url

    def test_post_with_in_use_destination_redirects_and_does_not_delete(
        self, admin_client, destination_in_use
    ):
        destination_id = destination_in_use.id
        url = reverse('forwarding:delete_destination', args=[destination_id])
        response = admin_client.post(url)
        assert response.status_code == 302
        assert reverse('forwarding:destinations') in response.url
        assert ForwardingDestination.objects.filter(id=destination_id).exists()

    def test_non_admin_get_redirects(self, regular_client, destination):
        url = reverse('forwarding:delete_destination', args=[destination.id])
        response = regular_client.get(url)
        assert response.status_code in (302, 403)

    def test_anonymous_get_redirects(self, client, destination):
        url = reverse('forwarding:delete_destination', args=[destination.id])
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url
