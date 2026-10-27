import pytest
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.users.models import CustomUser
from apps.users.setup import provision_admin

_monkeypatch = fixture('monkeypatch')
_caplog = fixture('caplog')

ADMIN_EMAIL = 'admin@example.com'
ADMIN_PASSWORD = 'S3curePass!23'


@fixture
def _client():
    yield Client()


def submit_setup(email=ADMIN_EMAIL, confirm=ADMIN_PASSWORD, **extra):
    return _client().post(
        reverse('setup'),
        {'email': email, 'password1': ADMIN_PASSWORD, 'password2': confirm},
        **extra,
    )


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
