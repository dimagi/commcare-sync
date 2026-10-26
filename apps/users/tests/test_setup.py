import pytest
from unmagic import fixture, use

from apps.users.models import CustomUser
from apps.users.setup import provision_admin

_caplog = fixture('caplog')

ADMIN_EMAIL = 'admin@example.com'
ADMIN_PASSWORD = 'S3curePass!23'


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

