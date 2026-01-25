from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.exports.models import (
    ExportConfig,
    ExportDatabase,
    ExportRun,
)
from apps.forwarding.models import (
    ForwardingConfig,
    ForwardingDestination,
    ForwardingRun,
)
from apps.web.views import _get_export_statistics, _get_forwarding_statistics

User = get_user_model()


class DashboardViewTestCase:
    def setup(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse('web:dashboard'))
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_dashboard_accessible_when_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('web:dashboard'))
        assert response.status_code == 200
        assert 'active_tab' in response.context
        assert response.context['active_tab'] == 'dashboard'

    def test_home_redirects_to_dashboard(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('web:home'))
        assert response.status_code == 302
        assert response.url == reverse('web:dashboard')

    def test_dashboard_displays_with_no_data(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('web:dashboard'))
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'forwarding_stats' in response.context
        assert response.context['export_stats']['total_configs'] == 0
        assert response.context['forwarding_stats']['total_configs'] == 0


class ExportStatisticsTestCase:
    def setup(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )

        self.server = CommCareServer.objects.create(
            url='https://commcarehq.org',
            name='CommCare HQ',
        )
        self.account = CommCareAccount.objects.create(
            server=self.server,
            username='test@account.com',
            api_key_encrypted='encrypted_key',
        )
        self.project = CommCareProject.objects.create(
            domain='test-domain',
            server=self.server,
        )

        self.database = ExportDatabase.objects.create(
            name='Test DB',
            owner=self.user,
        )
        self.database.connection_string = (
            'postgresql://user:pass@localhost:5432/db'
        )
        self.database.save()

        self.export_config = ExportConfig.objects.create(
            name='Test Export',
            account=self.account,
            project=self.project,
            database=self.database,
            created_by=self.user,
        )

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
                status=ExportRun.COMPLETED,
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
            status=ExportRun.COMPLETED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ExportRun.objects.create(
            base_export_config=self.export_config,
            status=ExportRun.FAILED,
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
            status=ExportRun.QUEUED,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ExportRun.objects.create(
            base_export_config=self.export_config,
            status=ExportRun.COMPLETED,
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
                status=ExportRun.COMPLETED,
                created_at=timezone.now() - timedelta(hours=i),
            )
        for i in range(failed):
            ExportRun.objects.create(
                base_export_config=self.export_config,
                status=ExportRun.FAILED,
                created_at=timezone.now() - timedelta(hours=successful + i),
            )

        stats = _get_export_statistics(last_24h)
        assert stats['success_rate'] == expected_rate
        assert stats['status'] == expected_status


class ForwardingStatisticsTestCase:
    def setup(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )

        self.database = ExportDatabase.objects.create(
            name='Test DB', owner=self.user
        )
        self.database.connection_string = (
            'postgresql://user:pass@localhost:5432/db'
        )
        self.database.save()

        self.destination = ForwardingDestination.objects.create(
            name='Test Destination',
            api_url='https://example.com/api',
            owner=self.user,
        )

        self.forwarding_config = ForwardingConfig.objects.create(
            name='Test Forwarding',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM table',
            created_by=self.user,
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
