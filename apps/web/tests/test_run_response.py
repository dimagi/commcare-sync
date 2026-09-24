from datetime import timedelta

from django.utils import timezone
from unmagic import use

from apps.commcare.models import RunBaseModel
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.web.views import already_running_message
from tests.fixtures import database, user


def _active_run(config, status, **kwargs):
    run = ForwardingRun.objects.create(config=config, status=status, **kwargs)
    ForwardingRun.objects.filter(pk=run.pk).update(
        created_at=timezone.now() - timedelta(minutes=2, seconds=5)
    )
    return run


@use(database, destination, forwarding_config)
class TestAlreadyRunningMessage:

    def test_names_the_user_who_requested_a_running_run(self):
        config = forwarding_config()
        _active_run(
            config, RunBaseModel.Status.STARTED, triggered_by=user()
        )

        assert already_running_message(config) == (
            'Not started: another run is already running. '
            'test@example.com requested it 2\xa0minutes ago.'
        )

    def test_says_when_a_queued_run_was_requested(self):
        config = forwarding_config()
        _active_run(config, RunBaseModel.Status.QUEUED)

        assert already_running_message(config) == (
            'Not started: another run is already waiting to start. '
            'It was requested 2\xa0minutes ago.'
        )

    def test_the_active_run_finished_in_the_meantime(self):
        config = forwarding_config()

        assert already_running_message(config) == (
            'Not started: another run was in progress.'
        )
