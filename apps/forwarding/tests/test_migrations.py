from importlib import import_module

from django.apps import apps
from unmagic import use

from apps.forwarding.models import ForwardingRun

from .fixtures import forwarding_config

rename_timeout_status = import_module(
    'apps.forwarding.migrations.0006_rename_timeout_status'
)


@use(forwarding_config)
class TestRenameTimeoutStatus:
    def test_timeout_rows_become_interrupted(self):
        run = ForwardingRun.objects.create(
            config=forwarding_config(), status='timeout'
        )
        rename_timeout_status.forwards(apps, None)
        run.refresh_from_db()
        assert run.status == ForwardingRun.Status.INTERRUPTED

    def test_reversal_restores_timeout(self):
        run = ForwardingRun.objects.create(
            config=forwarding_config(), status=ForwardingRun.Status.INTERRUPTED
        )
        rename_timeout_status.backwards(apps, None)
        run.refresh_from_db()
        assert run.status == 'timeout'
