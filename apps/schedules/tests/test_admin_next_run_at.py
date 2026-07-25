"""Verify next_run_at is actually rendered on the admin change form for
every ScheduleMixin config model, and that RefreshConfig can be paused
via schedule_enabled.

next_run_at is editable=False, so it must be explicitly listed in
readonly_fields to appear on the form at all - it is easy to add the
field to readonly_fields and have it silently do nothing if fieldsets
doesn't also list it (or if get_fields() isn't actually reached).
"""
from django.test import Client
from django.urls import reverse
from unmagic import use

from apps.exports.models import ExportConfig, MultiProjectExportConfig
from apps.exports.tests.fixtures import test_data
from apps.forwarding.tests.fixtures import forwarding_config
from apps.refreshes.tests.fixtures import refresh_config
from tests.fixtures import admin_user


@use('db')
class TestNextRunAtRendersOnAdminForms:

    def _client(self):
        client = Client()
        client.force_login(admin_user())
        return client

    def test_export_config_admin_shows_next_run_at(self):
        data = test_data()
        export = ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        response = self._client().get(
            reverse('admin:exports_exportconfig_change', args=[export.pk])
        )
        assert response.status_code == 200
        assert 'next_run_at' in response.content.decode()

    def test_multi_project_export_config_admin_shows_next_run_at(self):
        data = test_data()
        export = MultiProjectExportConfig.objects.create(
            name='Test Multi Export',
            account=data['account'],
            database=data['database'],
        )
        response = self._client().get(
            reverse(
                'admin:exports_multiprojectexportconfig_change',
                args=[export.pk],
            )
        )
        assert response.status_code == 200
        assert 'next_run_at' in response.content.decode()

    def test_forwarding_config_admin_shows_next_run_at(self):
        config = forwarding_config()
        response = self._client().get(
            reverse(
                'admin:forwarding_forwardingconfig_change', args=[config.pk]
            )
        )
        assert response.status_code == 200
        assert 'next_run_at' in response.content.decode()

    def test_refresh_config_admin_shows_next_run_at_and_schedule_enabled(
        self,
    ):
        config = refresh_config()
        response = self._client().get(
            reverse('admin:refreshes_refreshconfig_change', args=[config.pk])
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert 'next_run_at' in content
        # This is the actual pause affordance: without schedule_enabled in
        # the Scheduling fieldset, a RefreshConfig cannot be paused by any
        # means short of the shell.
        assert 'id_schedule_enabled' in content
