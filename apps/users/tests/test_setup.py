import pytest
from django.test import Client, RequestFactory
from django.urls import reverse
from unmagic import fixture, use

from apps.users.checks import check_setup_page_access
from apps.users.models import CustomUser
from apps.users.setup import provision_admin
from apps.users.views import first_run_setup
from commcare_sync.consts import SetupAccess

_settings = fixture('settings')
_monkeypatch = fixture('monkeypatch')
_caplog = fixture('caplog')

ADMIN_EMAIL = 'admin@example.com'
ADMIN_PASSWORD = 'S3curePass!23'


@fixture
@use(_settings)
def _client():
    # Requests arrive from loopback, for the host name a local browser
    # would use. The default access policy is 'loopback'.
    _settings().ALLOWED_HOSTS = ['localhost', '[::1]', 'sync.example.com']
    yield Client(HTTP_HOST='localhost')


def submit_setup(email=ADMIN_EMAIL, confirm=ADMIN_PASSWORD, **extra):
    return _client().post(
        reverse('setup'),
        {'email': email, 'password1': ADMIN_PASSWORD, 'password2': confirm},
        **extra,
    )


@fixture
@use(_settings)
def anyone():
    _settings().SETUP_PAGE_ACCESS = SetupAccess.ANYONE
    yield


@fixture
@use(_settings)
def nobody():
    _settings().SETUP_PAGE_ACCESS = SetupAccess.NOBODY
    yield


@use('db')
class TestProvisionAdmin:
    def test_creates_a_superuser(self):
        assert provision_admin(ADMIN_EMAIL, ADMIN_PASSWORD) is True

        user = CustomUser.objects.get(email=ADMIN_EMAIL)
        assert user.is_superuser
        assert user.check_password(ADMIN_PASSWORD)

    def test_does_nothing_when_a_user_exists(self):
        CustomUser.objects.create_user(
            email='someone@example.com', password='x'
        )

        assert provision_admin(ADMIN_EMAIL, ADMIN_PASSWORD) is False

        assert CustomUser.objects.count() == 1

    def test_does_nothing_without_credentials(self):
        assert provision_admin(None, None) is False

        assert not CustomUser.objects.exists()

    @use(_caplog)
    def test_warns_when_only_one_var_is_set(self):
        with _caplog().at_level('WARNING'):
            assert provision_admin(ADMIN_EMAIL, None) is False

        assert not CustomUser.objects.exists()
        assert 'must both be set' in _caplog().text

    @use(_caplog)
    @pytest.mark.parametrize(
        'email, password, complaint',
        [
            (ADMIN_EMAIL, 'password', 'too common'),
            (ADMIN_EMAIL, 'admin@example.com', 'too similar'),
            ('not-an-address', ADMIN_PASSWORD, 'valid email'),
        ],
    )
    def test_applies_the_same_validation_as_the_forms(
        self, email, password, complaint
    ):
        with _caplog().at_level('WARNING'):
            assert provision_admin(email, password) is False

        assert not CustomUser.objects.exists()
        assert complaint in _caplog().text


@use('db', _client)
class TestFirstRunSetupMiddleware:
    def test_redirects_everything_to_setup_until_a_user_exists(self):
        response = _client().get(reverse('login'))
        assert response.status_code == 302
        assert response.url == reverse('setup')

    def test_static_files_are_exempt(self):
        response = _client().get('/static/css/site.css')
        assert response.status_code != 302

    def test_passes_through_once_a_user_exists(self):
        CustomUser.objects.create_user(email='a@example.com', password='x')
        assert _client().get(reverse('login')).status_code == 200

    def test_setup_page_redirects_to_login_once_a_user_exists(self):
        CustomUser.objects.create_user(email='a@example.com', password='x')
        response = _client().get(reverse('setup'))
        assert response.status_code == 302
        assert response.url == reverse('login')


@use('db', _client)
class TestFirstRunSetupView:
    def test_renders_the_form(self):
        response = _client().get(reverse('setup'))
        assert response.status_code == 200
        assert b'name="email"' in response.content
        assert b'name="password1"' in response.content

    def test_creates_a_superuser_and_signs_them_in(self):
        response = submit_setup()

        assert response.status_code == 302
        assert response.url == '/'
        user = CustomUser.objects.get(email='admin@example.com')
        assert user.is_superuser
        assert user.is_staff
        assert user.check_password(ADMIN_PASSWORD)
        home = _client().get(reverse('web:home'), follow=True)
        assert home.redirect_chain == [(reverse('exports:home'), 302)]

    @use(_caplog)
    def test_the_creation_is_logged(self):
        with _caplog().at_level('WARNING'):
            submit_setup()
        assert 'Created the admin user admin@example.com' in _caplog().text

    def test_mismatched_passwords_create_nobody(self):
        response = submit_setup(confirm='something-else-entirely')
        assert response.status_code == 200
        assert not CustomUser.objects.exists()

    @use(_monkeypatch)
    def test_a_concurrent_submission_of_the_same_email_loses_cleanly(self):
        create_superuser = CustomUser.objects.create_superuser

        def other_submission_wins_the_race(email, password):
            CustomUser.objects.create_user(email=email, password='z')
            return create_superuser(email=email, password=password)

        _monkeypatch().setattr(
            CustomUser.objects,
            'create_superuser',
            other_submission_wins_the_race,
        )

        response = submit_setup()

        assert response.status_code == 302
        assert response.url == reverse('login')
        assert not CustomUser.objects.filter(is_superuser=True).exists()


@use('db', _client)
class TestSetupPageLoopbackByDefault:
    def test_a_remote_client_is_refused(self):
        response = _client().get(reverse('setup'), REMOTE_ADDR='10.0.0.5')
        assert response.status_code == 403
        assert b'COMMCARE_SYNC_ADMIN_EMAIL' in response.content
        assert b'from a browser running on the server' in response.content

    def test_a_remote_submission_creates_nobody(self):
        response = submit_setup(REMOTE_ADDR='10.0.0.5')
        assert response.status_code == 403
        assert not CustomUser.objects.exists()

    @pytest.mark.parametrize(
        'header',
        [
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_FORWARDED_HOST',
            'HTTP_X_FORWARDED_PROTO',
            'HTTP_FORWARDED',
            'HTTP_X_REAL_IP',
        ],
    )
    def test_a_forwarded_request_is_refused(self, header):
        # A proxy on this machine makes every visitor arrive from loopback.
        response = _client().get(reverse('setup'), **{header: '10.0.0.5'})
        assert response.status_code == 403

    def test_a_request_for_another_host_name_is_refused(self):
        # A page that rebinds its host name to 127.0.0.1 is not local.
        response = _client().get(
            reverse('setup'), HTTP_HOST='sync.example.com'
        )
        assert response.status_code == 403

    @pytest.mark.parametrize('address', ['127.0.0.1', '127.0.0.2', '::1'])
    def test_a_local_client_is_served(self, address):
        response = _client().get(reverse('setup'), REMOTE_ADDR=address)
        assert response.status_code == 200

    @pytest.mark.parametrize(
        'host', ['localhost', 'localhost:8000', '[::1]', '[::1]:8000']
    )
    def test_every_local_host_name_is_served(self, host):
        response = _client().get(reverse('setup'), HTTP_HOST=host)
        assert response.status_code == 200

    def test_the_view_refuses_a_remote_client_on_its_own(self):
        # Without the middleware: the view does not rely on it.
        request = RequestFactory().get(
            reverse('setup'), REMOTE_ADDR='10.0.0.5'
        )
        assert first_run_setup(request).status_code == 403


@use('db', _client, anyone)
class TestSetupPageAnyone:
    def test_a_remote_client_is_served(self):
        response = _client().get(reverse('setup'), REMOTE_ADDR='10.0.0.5')
        assert response.status_code == 200


@use('db', _client, nobody)
class TestSetupPageNobody:
    def test_a_local_client_is_refused(self):
        response = _client().get(reverse('setup'), REMOTE_ADDR='127.0.0.1')
        assert response.status_code == 403
        assert b'COMMCARE_SYNC_ADMIN_EMAIL' in response.content
        assert b'from a browser running on the server' not in response.content

    def test_a_local_submission_creates_nobody(self):
        response = submit_setup(REMOTE_ADDR='127.0.0.1')
        assert response.status_code == 403
        assert not CustomUser.objects.exists()


@use(_settings)
class TestSetupPageAccessCheck:
    def test_a_valid_value_passes(self):
        _settings().SETUP_PAGE_ACCESS = 'nobody'
        assert check_setup_page_access(None) == []

    def test_an_unknown_value_is_an_error(self):
        _settings().SETUP_PAGE_ACCESS = 'lopback'
        [error] = check_setup_page_access(None)
        assert 'lopback' in error.msg
