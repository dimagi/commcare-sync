from unmagic import use

from tests.fixtures import authed_client

from ..models import MultiProjectExportRun
from .fixtures import multi_export_config


@use(authed_client, multi_export_config)
class TestMultiProjectExportRunStatus:
    def test_reports_its_own_run(self):
        # A run that handed the button the single-project URL would poll
        # the wrong table and report on whichever ExportRun shares its id.
        run = MultiProjectExportRun.objects.create(
            config=multi_export_config(),
            status=MultiProjectExportRun.Status.COMPLETED,
        )
        assert authed_client().get(run.status_url).json() == {
            'status': 'completed',
            'label': 'Completed',
            'tone': 'success',
            'complete': True,
        }
