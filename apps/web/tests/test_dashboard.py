from datetime import timedelta

import pytest
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from unmagic import fixture, use

from apps.exports.models import (
    ExportConfig,
    ExportRun,
)
from apps.forwarding.models import (
    ForwardingConfig,
    ForwardingDestination,
    ForwardingRun,
)
from apps.refreshes.models import (
    RefreshConfig,
    RefreshRun,
)
from apps.web.views import _get_export_statistics, _get_forwarding_statistics, _get_refresh_statistics
from tests.fixtures import authed_client, commcare_account, commcare_project, database


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


@fixture
@use('db')
def destination():
    yield ForwardingDestination.objects.create(
        name='Test Destination',
        api_url='https://example.com/api',
    )


@fixture
def forwarding_config():
    yield ForwardingConfig.objects.create(
        name='Test Forwarding',
        database=database(),
        destination=destination(),
        query='SELECT * FROM table',
    )


@use('db')
class TestHomeView:
    @use(authed_client)
    def test_home_redirects_to_dashboard_when_authenticated(self):
        response = authed_client().get(reverse('web:home'))
        assert response.status_code == 302
        assert response.url == reverse('web:dashboard')

    def test_home_shows_landing_page_when_unauthenticated(self):
        response = Client().get(reverse('web:home'))
        assert response.status_code == 200


@use('db')
class TestExportStatistics:
    @use(export_config)
    def test_export_statistics_with_no_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)
        stats = _get_export_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 0
        assert stats['success_rate'] == 0
        assert stats['status'] == 'neutral'

    @use(export_config)
    def test_export_statistics_with_completed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(5):
            ExportRun.objects.create(
                base_export_config=export_config(),
                status=ExportRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )

        stats = _get_export_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 5
        assert stats['success_rate'] == 100.0
        assert stats['successful_count'] == 5
        assert stats['failed_count'] == 0
        assert stats['status'] == 'healthy'

    @use(export_config)
    def test_export_statistics_with_failed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_export_statistics(last_24h)

        assert stats['last_24h_runs'] == 2
        assert stats['success_rate'] == 50.0
        assert stats['successful_count'] == 1
        assert stats['failed_count'] == 1
        assert stats['status'] == 'error'

    @use(export_config)
    def test_export_statistics_excludes_queued_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_export_statistics(last_24h)

        assert stats['last_24h_runs'] == 1
        assert stats['success_rate'] == 100.0

    @pytest.mark.parametrize(
        'successful,failed,expected_rate,expected_status',
        [
            (19, 1, 95.0, 'healthy'),
            (17, 3, 85.0, 'warning'),
            (15, 5, 75.0, 'error'),
            (16, 4, 80.0, 'warning'),
            (20, 0, 100.0, 'healthy'),
        ],
    )
    @use(export_config)
    def test_export_statistics_status_thresholds(
        self, successful, failed, expected_rate, expected_status
    ):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(successful):
            ExportRun.objects.create(
                base_export_config=export_config(),
                status=ExportRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )
        for i in range(failed):
            ExportRun.objects.create(
                base_export_config=export_config(),
                status=ExportRun.Status.FAILED,
                created_at=timezone.now() - timedelta(hours=successful + i),
            )

        stats = _get_export_statistics(last_24h)
        assert stats['success_rate'] == expected_rate
        assert stats['status'] == expected_status


@use('db')
class TestRefreshStatistics:
    @use(refresh_config)
    def test_refresh_statistics_with_no_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)
        stats = _get_refresh_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 0
        assert stats['success_rate'] == 0
        assert stats['status'] == 'neutral'

    @use(refresh_config)
    def test_refresh_statistics_with_completed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(4):
            RefreshRun.objects.create(
                refresh_config=refresh_config(),
                status=RefreshRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )

        stats = _get_refresh_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 4
        assert stats['success_rate'] == 100.0
        assert stats['successful_count'] == 4
        assert stats['failed_count'] == 0
        assert stats['status'] == 'healthy'

    @use(refresh_config)
    def test_refresh_statistics_with_failed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        RefreshRun.objects.create(
            refresh_config=refresh_config(),
            status=RefreshRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        RefreshRun.objects.create(
            refresh_config=refresh_config(),
            status=RefreshRun.Status.FAILED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_refresh_statistics(last_24h)

        assert stats['last_24h_runs'] == 2
        assert stats['success_rate'] == 50.0
        assert stats['successful_count'] == 1
        assert stats['failed_count'] == 1
        assert stats['status'] == 'error'

    @use(refresh_config)
    def test_refresh_statistics_excludes_queued_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        RefreshRun.objects.create(
            refresh_config=refresh_config(),
            status=RefreshRun.Status.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        RefreshRun.objects.create(
            refresh_config=refresh_config(),
            status=RefreshRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_refresh_statistics(last_24h)

        assert stats['last_24h_runs'] == 1
        assert stats['success_rate'] == 100.0

    @pytest.mark.parametrize(
        'successful,failed,expected_rate,expected_status',
        [
            (19, 1, 95.0, 'healthy'),
            (17, 3, 85.0, 'warning'),
            (15, 5, 75.0, 'error'),
            (16, 4, 80.0, 'warning'),
            (20, 0, 100.0, 'healthy'),
        ],
    )
    @use(refresh_config)
    def test_refresh_statistics_status_thresholds(
        self, successful, failed, expected_rate, expected_status
    ):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(successful):
            RefreshRun.objects.create(
                refresh_config=refresh_config(),
                status=RefreshRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )
        for i in range(failed):
            RefreshRun.objects.create(
                refresh_config=refresh_config(),
                status=RefreshRun.Status.FAILED,
                created_at=timezone.now() - timedelta(hours=successful + i),
            )

        stats = _get_refresh_statistics(last_24h)
        assert stats['success_rate'] == expected_rate
        assert stats['status'] == expected_status


@use('db')
class TestForwardingStatistics:
    @use(forwarding_config)
    def test_forwarding_statistics_with_no_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)
        stats = _get_forwarding_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 0
        assert stats['success_rate'] == 0
        assert stats['status'] == 'neutral'

    @use(forwarding_config)
    def test_forwarding_statistics_with_completed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(3):
            ForwardingRun.objects.create(
                forwarding_config=forwarding_config(),
                status=ForwardingRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )

        stats = _get_forwarding_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 3
        assert stats['success_rate'] == 100.0
        assert stats['successful_count'] == 3
        assert stats['failed_count'] == 0
        assert stats['status'] == 'healthy'

    @use(forwarding_config)
    def test_forwarding_statistics_excludes_queued_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_forwarding_statistics(last_24h)

        assert stats['last_24h_runs'] == 1
        assert stats['success_rate'] == 100.0
