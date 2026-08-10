import pytest
from django.test import Client
from django.urls import reverse
from unmagic import use

from apps.exports.models import ExportRun
from apps.exports.tests.fixtures import export_config
from tests.fixtures import authed_client


@use(authed_client, export_config)
class TestRunStatus:
    @pytest.mark.parametrize('status, label, tone, complete', [
        (ExportRun.Status.QUEUED, 'Queued', 'secondary', False),
        (ExportRun.Status.STARTED, 'Started', 'primary', False),
        (ExportRun.Status.COMPLETED, 'Completed', 'success', True),
        (ExportRun.Status.FAILED, 'Failed', 'danger', True),
        (ExportRun.Status.TIMEOUT, 'Timed out', 'warning', True),
        (ExportRun.Status.SKIPPED, 'Skipped', 'secondary', True),
        (ExportRun.Status.MULTIPLE, 'Multiple statuses', 'warning', True),
    ])
    def test_reports_the_run_status(self, status, label, tone, complete):
        run = ExportRun.objects.create(config=export_config(), status=status)

        response = authed_client().get(run.status_url)

        assert response.json() == {
            'status': status.value,
            'label': label,
            'tone': tone,
            'complete': complete,
        }

    def test_response_is_not_cached(self):
        run = ExportRun.objects.create(
            config=export_config(), status=ExportRun.Status.QUEUED
        )

        response = authed_client().get(run.status_url)

        assert response['Cache-Control'] == 'no-store'

    def test_unknown_run_is_404(self):
        url = reverse('exports:run_status', args=[999999])
        assert authed_client().get(url).status_code == 404

    def test_requires_login(self):
        run = ExportRun.objects.create(
            config=export_config(), status=ExportRun.Status.QUEUED
        )
        assert Client().get(run.status_url).status_code == 302
