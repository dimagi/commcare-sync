"""Tests for the first-run setup page (apps/users/middleware.py,
apps/users/views.first_run_setup)."""

from django.urls import reverse
from unmagic import fixture, use

from apps.users.models import CustomUser

_client = fixture('client')

VALID_PASSWORD = 'S3curePass!23'  # noqa: S105 - test fixture password


@use('db', _client)
class TestFirstRunSetupMiddleware:
    def test_redirects_to_setup_when_no_users(self):
        response = _client().get(reverse('web:home'))
        assert response.status_code == 302
        assert response.url == reverse('setup')

    def test_setup_page_is_reachable_when_no_users(self):
        response = _client().get(reverse('setup'))
        assert response.status_code == 200

    def test_passes_through_when_users_exist(self):
        CustomUser.objects.create_user(email='a@example.com', password='x')

        response = _client().get(reverse('login'))

        assert response.status_code == 200

    def test_setup_url_redirects_away_when_users_exist(self):
        CustomUser.objects.create_user(email='a@example.com', password='x')

        response = _client().get(reverse('setup'))

        assert response.status_code == 302
        assert response.url == reverse('login')


@use('db', _client)
class TestFirstRunSetupView:
    def test_get_renders_form_when_no_users(self):
        response = _client().get(reverse('setup'))

        assert response.status_code == 200
        assert b'name="email"' in response.content
        assert b'name="password1"' in response.content

    def test_view_redirects_away_when_users_exist(self):
        CustomUser.objects.create_user(email='a@example.com', password='x')

        response = _client().get(reverse('setup'))

        assert response.status_code == 302
        assert response.url == reverse('login')

    def test_post_creates_superuser_logs_in_and_redirects_home(self):
        response = _client().post(
            reverse('setup'),
            {
                'email': 'admin@example.com',
                'password1': VALID_PASSWORD,
                'password2': VALID_PASSWORD,
            },
        )

        assert response.status_code == 302
        assert response.url == '/'

        user = CustomUser.objects.get(email='admin@example.com')
        assert user.is_superuser
        assert user.is_staff
        assert user.check_password(VALID_PASSWORD)

        # The user is logged in: a follow-up request is not bounced to
        # setup or login (home redirects an authenticated user on to
        # exports:home, which is what we're checking here).
        home = _client().get(reverse('web:home'), follow=True)
        assert home.status_code == 200
        assert home.redirect_chain == [(reverse('exports:home'), 302)]

    def test_password_mismatch_rerenders_with_error_and_creates_nobody(self):
        response = _client().post(
            reverse('setup'),
            {
                'email': 'admin@example.com',
                'password1': VALID_PASSWORD,
                'password2': 'something-else-entirely',
            },
        )

        assert response.status_code == 200
        assert not CustomUser.objects.exists()
        assert b'didn' in response.content  # "didn't match" error text

    def test_race_at_post_redirects_without_creating_a_second_user(
        self, monkeypatch
    ):
        """A user is created by someone else between this request's
        middleware check and the view's in-transaction re-check; the view
        must lose gracefully rather than create a second admin."""
        calls = {'n': 0}
        real_exists = CustomUser.objects.exists

        def fake_exists(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] < 3:
                return False
            CustomUser.objects.create_user(
                email='other@example.com', password='y'
            )
            return True

        monkeypatch.setattr(CustomUser.objects, 'exists', fake_exists)

        response = _client().post(
            reverse('setup'),
            {
                'email': 'admin@example.com',
                'password1': VALID_PASSWORD,
                'password2': VALID_PASSWORD,
            },
        )

        monkeypatch.setattr(CustomUser.objects, 'exists', real_exists)
        assert response.status_code == 302
        assert response.url == reverse('login')
        assert CustomUser.objects.count() == 1
        assert not CustomUser.objects.filter(
            email='admin@example.com'
        ).exists()
