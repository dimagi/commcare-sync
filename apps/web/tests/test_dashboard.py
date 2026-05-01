from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.db.models import Database
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
from apps.web.stats import _get_export_statistics, _get_forwarding_statistics, _get_refresh_statistics

User = get_user_model()


@pytest.mark.django_db
class TestHomeView:
    def setup_method(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )

    def test_home_redirects_to_exports_when_authenticated(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('web:home'))
        assert response.status_code == 302
        assert response.url == reverse('exports:home')

    def test_home_shows_landing_page_when_unauthenticated(self):
        response = self.client.get(reverse('web:home'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestExportStatistics:
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )

        self.server = CommCareServer.objects.create(
            url='https://commcarehq.org',
            name='CommCare HQ',
        )
        self.account = CommCareAccount.objects.create(
            server=self.server,
            username='test@account.com',
            api_key_encrypted='encrypted_key',
            owner=self.user,
        )
        self.project = CommCareProject.objects.create(
            domain='test-domain',
            server=self.server,
        )

        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://user:pass@localhost:5432/db',
        )

        config_file = TemporaryUploadedFile(
            name='config_file',
            content_type='application/xml',
            size=100,
            charset='utf-8',
        )
        self.export_config = ExportConfig.objects.create(
            name='Test Export',
            account=self.account,
            project=self.project,
            database=self.database,
            config_file=config_file,
        )
        config_file.close()

    def test_export_statistics_with_no_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)
        stats = _get_export_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 0
        assert stats['success_rate'] == 0
        assert stats['status'] == 'neutral'

    def test_export_statistics_with_completed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(5):
            ExportRun.objects.create(
                base_export_config=self.export_config,
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

    def test_export_statistics_with_failed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        ExportRun.objects.create(
            base_export_config=self.export_config,
            status=ExportRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ExportRun.objects.create(
            base_export_config=self.export_config,
            status=ExportRun.Status.FAILED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_export_statistics(last_24h)

        assert stats['last_24h_runs'] == 2
        assert stats['success_rate'] == 50.0
        assert stats['successful_count'] == 1
        assert stats['failed_count'] == 1
        assert stats['status'] == 'error'

    def test_export_statistics_excludes_queued_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        ExportRun.objects.create(
            base_export_config=self.export_config,
            status=ExportRun.Status.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ExportRun.objects.create(
            base_export_config=self.export_config,
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
    def test_export_statistics_status_thresholds(
        self, successful, failed, expected_rate, expected_status
    ):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(successful):
            ExportRun.objects.create(
                base_export_config=self.export_config,
                status=ExportRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )
        for i in range(failed):
            ExportRun.objects.create(
                base_export_config=self.export_config,
                status=ExportRun.Status.FAILED,
                created_at=timezone.now() - timedelta(hours=successful + i),
            )

        stats = _get_export_statistics(last_24h)
        assert stats['success_rate'] == expected_rate
        assert stats['status'] == expected_status


@pytest.mark.django_db
class TestRefreshStatistics:
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )

        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://user:pass@localhost:5432/db',
        )

        self.refresh_config = RefreshConfig.objects.create(
            name='Test Refresh',
            database=self.database,
            materialized_views=['public.test_view'],
        )

    def test_refresh_statistics_with_no_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)
        stats = _get_refresh_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 0
        assert stats['success_rate'] == 0
        assert stats['status'] == 'neutral'

    def test_refresh_statistics_with_completed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(4):
            RefreshRun.objects.create(
                refresh_config=self.refresh_config,
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

    def test_refresh_statistics_with_failed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        RefreshRun.objects.create(
            refresh_config=self.refresh_config,
            status=RefreshRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        RefreshRun.objects.create(
            refresh_config=self.refresh_config,
            status=RefreshRun.Status.FAILED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_refresh_statistics(last_24h)

        assert stats['last_24h_runs'] == 2
        assert stats['success_rate'] == 50.0
        assert stats['successful_count'] == 1
        assert stats['failed_count'] == 1
        assert stats['status'] == 'error'

    def test_refresh_statistics_excludes_queued_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        RefreshRun.objects.create(
            refresh_config=self.refresh_config,
            status=RefreshRun.Status.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        RefreshRun.objects.create(
            refresh_config=self.refresh_config,
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
    def test_refresh_statistics_status_thresholds(
        self, successful, failed, expected_rate, expected_status
    ):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(successful):
            RefreshRun.objects.create(
                refresh_config=self.refresh_config,
                status=RefreshRun.Status.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )
        for i in range(failed):
            RefreshRun.objects.create(
                refresh_config=self.refresh_config,
                status=RefreshRun.Status.FAILED,
                created_at=timezone.now() - timedelta(hours=successful + i),
            )

        stats = _get_refresh_statistics(last_24h)
        assert stats['success_rate'] == expected_rate
        assert stats['status'] == expected_status


@pytest.mark.django_db
class TestForwardingStatistics:
    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )

        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://user:pass@localhost:5432/db',
        )

        self.destination = ForwardingDestination.objects.create(
            name='Test Destination',
            api_url='https://example.com/api',
        )

        self.forwarding_config = ForwardingConfig.objects.create(
            name='Test Forwarding',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM table',
        )

    def test_forwarding_statistics_with_no_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)
        stats = _get_forwarding_statistics(last_24h)

        assert stats['total_configs'] == 1
        assert stats['last_24h_runs'] == 0
        assert stats['success_rate'] == 0
        assert stats['status'] == 'neutral'

    def test_forwarding_statistics_with_completed_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        for i in range(3):
            ForwardingRun.objects.create(
                forwarding_config=self.forwarding_config,
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

    def test_forwarding_statistics_excludes_queued_runs(self):
        last_24h = timezone.now() - timedelta(hours=24)

        ForwardingRun.objects.create(
            forwarding_config=self.forwarding_config,
            status=ForwardingRun.Status.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ForwardingRun.objects.create(
            forwarding_config=self.forwarding_config,
            status=ForwardingRun.Status.COMPLETED,
            created_at=timezone.now() - timedelta(hours=2),
        )

        stats = _get_forwarding_statistics(last_24h)

        assert stats['last_24h_runs'] == 1
        assert stats['success_rate'] == 100.0
