from unittest.mock import patch

import pytest
from django.db.models import QuerySet
from unmagic import fixture, use

from apps.commcare.models import RunBaseModel
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.schedules.dispatch import (
    claim_run,
    create_run,
    create_run_and_dispatch,
)
from tests.fixtures import database, user


@fixture
def mock_async():
    with patch('apps.schedules.dispatch.async_task') as mock:
        mock.return_value = 'task-id'
        yield mock


@use(database, destination, forwarding_config)
class TestCreateRun:

    def test_creates_a_run_for_the_config(self):
        config = forwarding_config()

        run = create_run(config)

        assert isinstance(run, ForwardingRun)
        assert run.config == config
        assert run.status == RunBaseModel.Status.QUEUED
        assert run.config_version == config.latest_version

    def test_records_attribution(self):
        config = forwarding_config()
        triggering_user = user()

        run = create_run(
            config, triggered_from_ui=True, triggered_by=triggering_user
        )

        assert run.triggered_from_ui is True
        assert run.triggered_by == triggering_user

    def test_defaults_to_not_triggered_from_ui(self):
        run = create_run(forwarding_config())

        assert run.triggered_from_ui is False
        assert run.triggered_by is None

    def test_returns_none_when_a_run_is_queued(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.QUEUED
        )

        assert create_run(config) is None
        assert config.runs.count() == 1

    def test_returns_none_when_a_run_is_started(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.STARTED
        )

        assert create_run(config) is None
        assert config.runs.count() == 1

    def test_allows_a_run_when_the_last_one_finished(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.COMPLETED
        )

        assert create_run(config) is not None


@use(database, destination, forwarding_config, mock_async)
class TestCreateRunAndDispatch:

    def test_enqueues_the_task_with_the_run_id(self):
        config = forwarding_config()

        task_id = create_run_and_dispatch(
            config, triggered_from_ui=True
        )

        assert task_id == 'task-id'
        mock_async().assert_called_once_with(
            'apps.forwarding.tasks.run_forwarding_task', config.runs.get().id
        )

    def test_marks_the_run_as_ui_triggered(self):
        config = forwarding_config()
        triggering_user = user()

        create_run_and_dispatch(
            config,
            triggered_from_ui=True,
            triggered_by=triggering_user,
        )

        run = config.runs.get()
        assert run.triggered_from_ui is True
        assert run.triggered_by == triggering_user

    def test_passes_task_kwargs_to_the_task(self):
        config = forwarding_config()

        create_run_and_dispatch(
            config,
            triggered_from_ui=True,
            task_kwargs={'start_over': True},
        )

        mock_async().assert_called_once_with(
            'apps.forwarding.tasks.run_forwarding_task',
            config.runs.get().id,
            start_over=True,
        )

    def test_enqueues_nothing_when_a_run_is_active(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.STARTED
        )

        task_id = create_run_and_dispatch(
            config, triggered_from_ui=True
        )

        assert task_id is None
        assert config.runs.count() == 1
        mock_async().assert_not_called()

    def test_run_is_rolled_back_if_the_task_cannot_be_queued(self):
        config = forwarding_config()
        mock_async().side_effect = RuntimeError('queue unavailable')

        with pytest.raises(RuntimeError):
            create_run_and_dispatch(
                config, triggered_from_ui=True
            )

        assert config.runs.count() == 0


@use(database, destination, forwarding_config)
class TestClaimRun:

    def _claim(self, run):
        return claim_run(ForwardingRun, run.id)

    def test_first_delivery_claims_the_queued_run(self):
        run = ForwardingRun.objects.create(config=forwarding_config())

        claimed = self._claim(run)

        assert claimed == run
        assert claimed.status == RunBaseModel.Status.STARTED
        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.STARTED
        assert run.started_at == claimed.started_at is not None

    def test_a_run_skipped_after_it_was_read_is_not_claimed(self):
        # A queued run can be marked SKIPPED between claim_run reading it
        # and starting it. The start is conditional, so it doesn't
        # overwrite SKIPPED.
        run = ForwardingRun.objects.create(config=forwarding_config())
        stale = ForwardingRun.objects.get(pk=run.pk)
        ForwardingRun.objects.filter(pk=run.pk).update(
            status=RunBaseModel.Status.SKIPPED
        )
        with patch.object(QuerySet, 'get', return_value=stale):
            claimed = claim_run(ForwardingRun, run.id)

        assert claimed is None
        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.SKIPPED

    def test_missing_run_logs_and_returns_none(self, caplog):
        assert claim_run(ForwardingRun, 999999) is None
        assert 'ForwardingRun 999999 no longer exists' in caplog.text

    @pytest.mark.parametrize('status', [
        RunBaseModel.Status.STARTED,
        RunBaseModel.Status.COMPLETED,
        RunBaseModel.Status.FAILED,
        RunBaseModel.Status.SKIPPED,
    ])
    def test_redelivery_does_not_redo_the_work(self, status):
        run = ForwardingRun.objects.create(
            config=forwarding_config(), status=status
        )

        assert self._claim(run) is None
        assert ForwardingRun.objects.count() == 1

    def test_timed_out_run_is_retried_as_a_new_run(self):
        triggering_user = user()
        run = ForwardingRun.objects.create(
            config=forwarding_config(),
            status=RunBaseModel.Status.TIMEOUT,
            triggered_from_ui=True,
            triggered_by=triggering_user,
        )

        retry = self._claim(run)

        assert retry is not None
        assert retry != run
        assert retry.retry_of == run
        # Performed at once by this delivery, so never left QUEUED.
        assert retry.status == RunBaseModel.Status.STARTED
        assert retry.started_at is not None
        assert retry.config == run.config
        assert retry.triggered_from_ui is True
        assert retry.triggered_by == triggering_user

    def test_timed_out_run_is_retried_only_once(self):
        # Django Q2 keeps delivering a task whose worker was killed, with
        # the same, original run ID. Only the first re-delivery retries.
        run = ForwardingRun.objects.create(
            config=forwarding_config(), status=RunBaseModel.Status.TIMEOUT
        )
        retry = self._claim(run)
        ForwardingRun.objects.filter(pk=retry.pk).update(
            status=RunBaseModel.Status.TIMEOUT
        )

        assert self._claim(run) is None
        assert ForwardingRun.objects.count() == 2

    def test_a_retry_is_never_retried(self):
        config = forwarding_config()
        original = ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.TIMEOUT
        )
        retry = ForwardingRun.objects.create(
            config=config,
            status=RunBaseModel.Status.TIMEOUT,
            retry_of=original,
        )

        assert self._claim(retry) is None
        assert ForwardingRun.objects.count() == 2

    def test_timed_out_run_is_not_retried_while_another_run_is_active(self):
        config = forwarding_config()
        run = ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.TIMEOUT
        )
        ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.STARTED
        )

        assert self._claim(run) is None
        assert ForwardingRun.objects.count() == 2
