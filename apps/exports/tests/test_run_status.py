from django.test import Client
from django.urls import reverse
from unmagic import use

from tests.fixtures import authed_client

from ..models import ExportRun, MultiProjectExportRun
from .fixtures import export_config, multi_export_config


@use(authed_client, export_config)
class TestExportRunStatus:
    def _run(self, status):
        config = export_config()
        return ExportRun.objects.create(config=config, status=status)

    def test_active_run_is_not_complete(self):
        run = self._run(ExportRun.Status.QUEUED)
        response = authed_client().get(run.status_url)
        assert response.status_code == 200
        assert response.json() == {
            'status': 'queued',
            'label': 'Queued',
            'complete': False,
        }

    def test_started_run_labels_itself(self):
        # QUEUED and STARTED are distinguishable for the first time:
        # the old endpoint reported both as "Running...".
        run = self._run(ExportRun.Status.STARTED)
        assert authed_client().get(run.status_url).json() == {
            'status': 'started',
            'label': 'Started',
            'complete': False,
        }

    def test_completed_run_is_complete(self):
        run = self._run(ExportRun.Status.COMPLETED)
        assert authed_client().get(run.status_url).json() == {
            'status': 'completed',
            'label': 'Completed',
            'complete': True,
        }

    def test_failed_run_is_complete(self):
        run = self._run(ExportRun.Status.FAILED)
        body = authed_client().get(run.status_url).json()
        assert body['status'] == 'failed'
        assert body['complete'] is True

    def test_timeout_and_skipped_are_complete_but_not_failures(self):
        # Both arrive out of band -- TIMEOUT from reap_stale_runs,
        # SKIPPED from clear_queued_runs -- and neither is a failure.
        for status, label in [
            (ExportRun.Status.TIMEOUT, 'Timed out'),
            (ExportRun.Status.SKIPPED, 'Skipped'),
        ]:
            body = authed_client().get(self._run(status).status_url).json()
            assert body == {
                'status': status.value,
                'label': label,
                'complete': True,
            }

    def test_multiple_is_complete_and_labelled_by_result(self):
        run = self._run(ExportRun.Status.MULTIPLE)
        assert authed_client().get(run.status_url).json() == {
            'status': 'multiple',
            'label': 'Multiple results',
            'complete': True,
        }

    def test_response_is_not_cached(self):
        run = self._run(ExportRun.Status.QUEUED)
        response = authed_client().get(run.status_url)
        assert response['Cache-Control'] == 'no-store'

    def test_unknown_run_is_404(self):
        url = reverse('exports:run_status', args=[999999])
        assert authed_client().get(url).status_code == 404

    def test_requires_login(self):
        run = self._run(ExportRun.Status.QUEUED)
        assert Client().get(run.status_url).status_code == 302


@use(authed_client, multi_export_config)
class TestMultiProjectExportRunStatus:
    def test_status_url_points_at_the_multi_project_endpoint(self):
        # A run that handed the button the single-project URL would poll
        # the wrong table and report on whichever ExportRun shares its id.
        run = MultiProjectExportRun.objects.create(
            config=multi_export_config(),
            status=MultiProjectExportRun.Status.QUEUED,
        )
        assert run.status_url == reverse(
            'exports:multi_run_status', args=[run.id]
        )

    def test_reports_its_own_run(self):
        run = MultiProjectExportRun.objects.create(
            config=multi_export_config(),
            status=MultiProjectExportRun.Status.COMPLETED,
        )
        assert authed_client().get(run.status_url).json() == {
            'status': 'completed',
            'label': 'Completed',
            'complete': True,
        }
