"""Tests for CustomUser model."""

from django.contrib.auth import get_user_model

User = get_user_model()


class TestCustomUserIsAdmin:
    """Tests for CustomUser.is_admin property"""

    def test_is_admin_when_active_superuser_and_staff(self):
        """User is admin when active, superuser, and staff"""
        user = User(
            username='admin_user',
            email='admin@example.com',
            is_active=True,
            is_superuser=True,
            is_staff=True,
        )
        assert user.is_admin is True

    def test_is_admin_false_when_not_superuser(self):
        """User is not admin when missing superuser flag"""
        user = User(
            username='not_admin_1',
            email='notadmin1@example.com',
            is_active=True,
            is_superuser=False,
            is_staff=True,
        )
        assert user.is_admin is False

    def test_is_admin_false_when_not_staff(self):
        """User is not admin when missing staff flag"""
        user = User(
            username='not_admin_2',
            email='notadmin2@example.com',
            is_active=True,
            is_superuser=True,
            is_staff=False,
        )
        assert user.is_admin is False

    def test_is_admin_false_when_inactive(self):
        """User is not admin when inactive"""
        user = User(
            username='inactive_user',
            email='inactive@example.com',
            is_active=False,
            is_superuser=True,
            is_staff=True,
        )
        assert user.is_admin is False


class TestCustomUserStr:
    """Tests for CustomUser.__str__ method"""

    def test_str_returns_email(self):
        """__str__ returns the user's email"""
        user = User(username='testuser', email='test@example.com')
        assert str(user) == 'test@example.com'


class TestCustomUserGetDisplayName:
    """Tests for CustomUser.get_display_name method"""

    def test_get_display_name_returns_full_name_when_set(self):
        """get_display_name returns full name if set"""
        user = User(
            username='john_doe',
            email='john@example.com',
            first_name='John',
            last_name='Doe',
        )
        assert user.get_display_name() == 'John Doe'

    def test_get_display_name_returns_email_when_full_name_empty(self):
        """get_display_name returns email when full name is empty"""
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='',
            last_name='',
        )
        assert user.get_display_name() == 'test@example.com'

    def test_get_display_name_returns_email_when_only_first_name(self):
        """get_display_name returns full name even with only first name"""
        user = User(
            username='john',
            email='john@example.com',
            first_name='John',
            last_name='',
        )
        assert user.get_display_name() == 'John'

    def test_get_display_name_returns_email_when_full_name_is_whitespace(self):
        """get_display_name returns email when full name is only whitespace"""
        user = User(
            username='testuser_ws',
            email='test@example.com',
            first_name='   ',
            last_name='',
        )
        assert user.get_display_name() == 'test@example.com'
