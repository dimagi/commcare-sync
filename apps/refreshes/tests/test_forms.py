import json

from unmagic import use

from apps.db.models import Database
from tests.fixtures import database

from ..forms import RefreshConfigForm
from ..models import RefreshConfig


@use('db')
class TestRefreshConfigForm:
    def _base_form_data(self, db_obj, **overrides):
        data = {
            'name': 'My Refresh',
            'database': db_obj.id,
            'materialized_views': json.dumps(['public.view1']),
            'first_run_time': '00:00',
            'timezone': 'UTC',
        }
        data.update(overrides)
        return data

    @use(database)
    def test_create_with_valid_data(self):
        form_data = self._base_form_data(
            database(),
            materialized_views=json.dumps(
                ['public.view1', 'public.view2']
            ),
        )
        form = RefreshConfigForm(form_data)

        assert form.is_valid(), form.errors

        config = form.save()

        assert config.name == 'My Refresh'
        assert config.materialized_views == ['public.view1', 'public.view2']

    @use(database)
    def test_create_missing_views_shows_form_error(self):
        form_data = self._base_form_data(
            database(), materialized_views=''
        )
        form = RefreshConfigForm(form_data)

        assert not form.is_valid()
        assert 'materialized_views' in form.errors

    @use(database)
    def test_create_empty_views_list_shows_form_error(self):
        form_data = self._base_form_data(
            database(), materialized_views=json.dumps([])
        )
        form = RefreshConfigForm(form_data)

        assert not form.is_valid()
        assert 'materialized_views' in form.errors

    @use(database)
    def test_create_invalid_json_shows_form_error(self):
        form_data = self._base_form_data(
            database(), materialized_views='not json'
        )
        form = RefreshConfigForm(form_data)

        assert not form.is_valid()
        assert 'materialized_views' in form.errors

    def test_create_rejects_non_postgresql_database(self):
        mysql_db = Database.objects.create(
            name='MySQL DB',
            connection_string='mysql://localhost/test',
        )
        form_data = {
            'name': 'My Refresh',
            'database': mysql_db.id,
            'materialized_views': json.dumps(['public.view1']),
            'first_run_time': '00:00',
            'timezone': 'UTC',
        }
        form = RefreshConfigForm(form_data)

        assert not form.is_valid()
        assert 'database' in form.errors

    @use(database)
    def test_edit_populates_materialized_views(self):
        db_obj = database()
        config = RefreshConfig.objects.create(
            name='Existing',
            database=db_obj,
            materialized_views=['public.view1', 'schema.view2'],
        )

        form = RefreshConfigForm(instance=config)

        assert form.initial['materialized_views'] == json.dumps(
            ['public.view1', 'schema.view2']
        )

    @use(database)
    def test_edit_saves_updated_views(self):
        db_obj = database()
        config = RefreshConfig.objects.create(
            name='Existing',
            database=db_obj,
            materialized_views=['public.view1'],
        )

        form_data = self._base_form_data(
            db_obj,
            name='Existing',
            materialized_views=json.dumps(
                ['public.view1', 'public.view2']
            ),
        )
        form = RefreshConfigForm(form_data, instance=config)

        assert form.is_valid(), form.errors

        updated = form.save()
        updated.refresh_from_db()
        assert updated.materialized_views == ['public.view1', 'public.view2']
