from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.db.forms import CreateDatabaseForm, EditDatabaseForm
from apps.db.models import Database


class TestDatabaseForm(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )

    def test_create_form_requires_connection_string(self):
        form = CreateDatabaseForm(data={
            'name': 'Test DB',
            'connection_string': '',
        })
        assert not form.is_valid()
        assert 'connection_string' in form.errors
        assert 'This field is required.' in str(form.errors['connection_string'])

    def test_create_form_with_connection_string(self):
        form = CreateDatabaseForm(data={
            'name': 'Test DB',
            'connection_string': 'postgresql://localhost/test',
        })
        assert form.is_valid()

    def test_edit_form_allows_empty_connection_string(self):
        db = Database.objects.create(
            name='Existing DB',
            owner=self.user,
        )
        db.connection_string = 'postgresql://localhost/original'
        db.save()

        form = EditDatabaseForm(
            data={
                'name': 'Updated Name',
                'connection_string': '',
            },
            instance=db
        )
        assert form.is_valid()

        # Save and verify connection_string wasn't changed
        updated_db = form.save()
        assert updated_db.name == 'Updated Name'
        assert updated_db.connection_string == 'postgresql://localhost/original'

    def test_edit_form_updates_connection_string_when_provided(self):
        db = Database.objects.create(
            name='Existing DB',
            owner=self.user,
        )
        db.connection_string = 'postgresql://localhost/original'
        db.save()

        form = EditDatabaseForm(
            data={
                'name': 'Updated Name',
                'connection_string': 'postgresql://localhost/updated',
            },
            instance=db
        )
        assert form.is_valid()

        # Save and verify connection_string was changed
        updated_db = form.save()
        assert updated_db.name == 'Updated Name'
        assert updated_db.connection_string == 'postgresql://localhost/updated'
