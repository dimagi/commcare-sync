import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from unmagic import use


@use('db')
def test_promote_promotes_existing_user():
    User = get_user_model()
    user = User.objects.create_user(email='target@example.com', password='x')
    assert not user.is_superuser

    stdout = io.StringIO()
    call_command(
        'promote_user_to_superuser',
        'Target@Example.COM',
        stdout=stdout,
    )

    user.refresh_from_db()
    assert user.is_superuser
    assert user.is_staff
    assert 'target@example.com' in stdout.getvalue()


@use('db')
def test_promote_raises_for_unknown_email():
    with pytest.raises(CommandError):
        call_command('promote_user_to_superuser', 'nope@example.com')
