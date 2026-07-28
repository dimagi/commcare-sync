from datetime import timedelta

from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from unmagic import fixture, use

from apps.exports.models import ExportConfig, ExportRun
from apps.refreshes.models import RefreshConfig, RefreshRun
from apps.web.failed_runs import recent_failed_runs
from tests.fixtures import (
    authed_client,
    commcare_account,
    commcare_project,
    database,
    user,
)


@fixture
def export_config():
    config_file = TemporaryUploadedFile(
        name='config_file',
        content_type='application/xml',
        size=100,
        charset='utf-8',
    )
    cfg = ExportConfig.objects.create(
        name='Test Export',
        account=commcare_account(),
        project=commcare_project(),
        database=database(),
        config_file=config_file,
    )
    config_file.close()
    yield cfg


@fixture
def refresh_config():
    yield RefreshConfig.objects.create(
        name='Test Refresh',
        database=database(),
        materialized_views=['public.test_view'],
    )


@use('db')
class TestRecentFailedRuns:
    @use(export_config, refresh_config)
    def test_collects_failures_across_models_within_window(self):
        since = timezone.now() - timedelta(hours=24)

        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            completed_at=timezone.now() - timedelta(hours=1),
        )
        RefreshRun.objects.create(
            refresh_config=refresh_config(),
            status=RefreshRun.Status.FAILED,
            completed_at=timezone.now() - timedelta(hours=2),
        )

        data = recent_failed_runs(since)

        assert data['total_count'] == 2
        assert len(data['entries']) == 2
        labels = {entry.label for entry in data['entries']}
        assert labels == {'Test Export', 'Test Refresh'}

    @use(export_config)
    def test_excludes_successful_runs(self):
        since = timezone.now() - timedelta(hours=24)
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.COMPLETED,
            completed_at=timezone.now() - timedelta(hours=1),
        )

        data = recent_failed_runs(since)

        assert data['total_count'] == 0
        assert data['entries'] == []

    @use(export_config)
    def test_excludes_failures_before_the_window(self):
        since = timezone.now() - timedelta(hours=24)
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            completed_at=timezone.now() - timedelta(hours=48),
        )

        data = recent_failed_runs(since)

        assert data['total_count'] == 0
        assert data['entries'] == []


@use('db')
class TestFailedRunsBannerContextProcessor:
    @use(user)
    def test_anonymous_user_gets_no_banner(self):
        user()
        response = Client().get(reverse('web:home'))
        assert 'failed_runs_banner' not in response.context

    @use(authed_client, export_config)
    def test_authenticated_user_with_recent_failure_sees_banner(self):
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            completed_at=timezone.now() - timedelta(hours=1),
        )

        response = authed_client().get(reverse('exports:home'))

        banner = response.context['failed_runs_banner']
        assert banner['total_count'] == 1
        assert banner['entries'][0].label == 'Test Export'

    @use(authed_client, export_config)
    def test_dismissal_hides_banner_until_a_new_failure(self):
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            completed_at=timezone.now() - timedelta(hours=1),
        )

        client = authed_client()
        response = client.get(reverse('exports:home'))
        assert 'failed_runs_banner' in response.context

        dismiss_response = client.post(
            reverse('web:dismiss_failed_runs_banner')
        )
        assert dismiss_response.status_code == 204

        response = client.get(reverse('exports:home'))
        assert 'failed_runs_banner' not in response.context

        # A new failure after dismissal must re-raise the banner.
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            completed_at=timezone.now(),
        )
        response = client.get(reverse('exports:home'))
        banner = response.context['failed_runs_banner']
        assert banner['total_count'] == 1


@use('db')
class TestDismissFailedRunsBannerView:
    @use(user)
    def test_requires_login(self):
        user()
        response = Client().post(reverse('web:dismiss_failed_runs_banner'))
        assert response.status_code == 302

    @use(authed_client)
    def test_post_sets_session_dismissal_timestamp(self):
        client = authed_client()
        response = client.post(reverse('web:dismiss_failed_runs_banner'))
        assert response.status_code == 204
        assert 'failed_runs_dismissed_at' in client.session
