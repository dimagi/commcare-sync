"""Tests for CustomUser model."""

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from unmagic import use

User = get_user_model()


@use('db')
def test_authenticate_by_email():
    User.objects.create_user(
        email='alice@example.com',
        password='hunter2',
    )
    user = authenticate(username='alice@example.com', password='hunter2')
    assert user is not None
    assert user.email == 'alice@example.com'


@use('db')
def test_email_is_lowercased_on_save():
    user = User.objects.create_user(
        email='Casey@Example.COM', password='hunter2',
    )
    user.refresh_from_db()
    assert user.email == 'casey@example.com'


@use('db')
def test_authenticate_is_case_insensitive():
    User.objects.create_user(
        email='dana@example.com', password='hunter2',
    )
    user = authenticate(username='Dana@Example.COM', password='hunter2')
    assert user is not None
    assert user.email == 'dana@example.com'


@use('db')
def test_manager_create_user_normalizes_email():
    user = User.objects.create_user(email='Erin@Example.COM', password='hunter2')
    user.refresh_from_db()
    assert user.email == 'erin@example.com'
    assert user.check_password('hunter2')
    assert not user.is_staff
    assert not user.is_superuser


@use('db')
def test_manager_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email='', password='hunter2')


@use('db')
def test_manager_create_superuser_sets_flags():
    user = User.objects.create_superuser(email='admin@example.com', password='hunter2')
    assert user.is_staff
    assert user.is_superuser


@use('db')
def test_manager_create_superuser_rejects_non_staff():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email='admin@example.com', password='hunter2', is_staff=False,
        )


@use('db')
def test_manager_create_superuser_rejects_non_superuser():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email='admin@example.com', password='hunter2', is_superuser=False,
        )


@use('db')
def test_email_must_be_unique():
    User.objects.create_user(
        email='dup@example.com', password='hunter2',
    )
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email='dup@example.com', password='hunter2',
        )


class TestCustomUserIsAdmin:
    """Tests for CustomUser.is_admin property"""

    def test_is_admin_when_active_superuser_and_staff(self):
        """User is admin when active, superuser, and staff"""
        user = User(
            email='admin@example.com',
            is_active=True,
            is_superuser=True,
            is_staff=True,
        )
        assert user.is_admin is True

    def test_is_admin_false_when_not_superuser(self):
        """User is not admin when missing superuser flag"""
        user = User(
            email='notadmin1@example.com',
            is_active=True,
            is_superuser=False,
            is_staff=True,
        )
        assert user.is_admin is False

    def test_is_admin_false_when_not_staff(self):
        """User is not admin when missing staff flag"""
        user = User(
            email='notadmin2@example.com',
            is_active=True,
            is_superuser=True,
            is_staff=False,
        )
        assert user.is_admin is False

    def test_is_admin_false_when_inactive(self):
        """User is not admin when inactive"""
        user = User(
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
        user = User(email='test@example.com')
        assert str(user) == 'test@example.com'


class TestCustomUserGetDisplayName:
    """Tests for CustomUser.get_display_name method"""

    def test_get_display_name_returns_full_name_when_set(self):
        """get_display_name returns full name if set"""
        user = User(
            email='john@example.com',
            first_name='John',
            last_name='Doe',
        )
        assert user.get_display_name() == 'John Doe'

    def test_get_display_name_returns_email_when_full_name_empty(self):
        """get_display_name returns email when full name is empty"""
        user = User(
            email='test@example.com',
            first_name='',
            last_name='',
        )
        assert user.get_display_name() == 'test@example.com'

    def test_get_display_name_returns_email_when_only_first_name(self):
        """get_display_name returns full name even with only first name"""
        user = User(
            email='john@example.com',
            first_name='John',
            last_name='',
        )
        assert user.get_display_name() == 'John'

    def test_get_display_name_returns_email_when_full_name_is_whitespace(self):
        """get_display_name returns email when full name is only whitespace"""
        user = User(
            email='test@example.com',
            first_name='   ',
            last_name='',
        )
        assert user.get_display_name() == 'test@example.com'
