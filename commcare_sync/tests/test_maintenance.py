import os

from django.utils import timezone
from django_q.brokers import get_broker
from django_q.models import OrmQ
from django_q.signing import SignedPackage
from unmagic import fixture, use

from apps.commcare.models import RunBaseModel
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.schedules.dispatch import claim_run, create_run_and_dispatch
from apps.users.models import CustomUser
from apps.users.setup import ADMIN_EMAIL_VAR, ADMIN_PASSWORD_VAR
from commcare_sync.launcher.maintenance import (
    create_admin_from_environment,
    repair_task_queue,
)
from tests.fixtures import database

_caplog = fixture('caplog')
_monkeypatch = fixture('monkeypatch')


@use(database, destination, forwarding_config)
class TestStartupMaintenance:
    def enqueue_and_take(self):
        run = create_run_and_dispatch(
            forwarding_config(), triggered_from_ui=False
        )
        [(_ack_id, payload)] = get_broker().dequeue()  # a worker took it
        return run, SignedPackage.loads(payload)

    def test_a_run_interrupted_by_a_dead_worker_is_retried_once(self):
        run, task = self.enqueue_and_take()
        ForwardingRun.objects.filter(pk=run.pk).update(
            status=RunBaseModel.Status.STARTED, started_at=timezone.now()
        )

        repair_task_queue()

        [(_ack_id, payload)] = get_broker().dequeue()  # delivered again
        assert (
            SignedPackage.loads(payload)['args'] == task['args'] == (run.id,)
        )
        retry = claim_run(ForwardingRun, run.id)
        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.INTERRUPTED
        assert retry.retry_of == run
        assert retry.status == RunBaseModel.Status.STARTED
        assert claim_run(ForwardingRun, run.id) is None  # not twice
        assert ForwardingRun.objects.count() == 2

    def test_a_run_whose_task_was_acknowledged_stays_interrupted(self):
        run, _task = self.enqueue_and_take()
        ForwardingRun.objects.filter(pk=run.pk).update(
            status=RunBaseModel.Status.STARTED, started_at=timezone.now()
        )
        OrmQ.objects.all().delete()  # the worker acknowledged, then died

        repair_task_queue()

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.INTERRUPTED
        assert get_broker().queue_size() == 0
        assert ForwardingRun.objects.count() == 1

    def test_a_finished_run_whose_task_was_not_acknowledged_is_not_redone(
        self,
    ):
        run, _task = self.enqueue_and_take()
        ForwardingRun.objects.filter(pk=run.pk).update(
            status=RunBaseModel.Status.COMPLETED, started_at=timezone.now()
        )

        repair_task_queue()

        assert get_broker().dequeue()  # delivered again
        assert claim_run(ForwardingRun, run.id) is None
        assert ForwardingRun.objects.count() == 1


@use(database, _monkeypatch)
def test_the_admin_credentials_are_removed_from_the_environment():
    # The task cluster and every commcare-export it starts inherit the
    # launcher's environment.
    _monkeypatch().setenv(ADMIN_EMAIL_VAR, 'admin@example.com')
    _monkeypatch().setenv(ADMIN_PASSWORD_VAR, 'S3curePass!23')
    create_admin_from_environment()
    assert ADMIN_EMAIL_VAR not in os.environ
    assert ADMIN_PASSWORD_VAR not in os.environ


@use(database, _caplog, _monkeypatch)
def test_what_maintenance_did_reaches_the_launcher_log():
    # The app's logging keeps WARNING and above; the launcher's keeps INFO.
    _monkeypatch().setenv(ADMIN_EMAIL_VAR, 'admin@example.com')
    _monkeypatch().setenv(ADMIN_PASSWORD_VAR, 'S3curePass!23')
    with _caplog().at_level('INFO', logger='commcare_sync.launcher'):
        create_admin_from_environment()
    assert CustomUser.objects.filter(is_superuser=True).exists()
    [record] = _caplog().records
    assert record.name == 'commcare_sync.launcher.maintenance'
    assert 'Created the admin user' in record.message
