from unittest.mock import patch

from unmagic import fixture, use

from apps.commcare.models import RunBaseModel
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.schedules.dispatch import create_run, create_run_and_dispatch
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

        run, task_id = create_run_and_dispatch(config, 'some.task')

        assert task_id == 'task-id'
        mock_async().assert_called_once_with('some.task', run.id)

    def test_marks_the_run_as_ui_triggered(self):
        triggering_user = user()

        run, _ = create_run_and_dispatch(
            forwarding_config(), 'some.task', triggered_by=triggering_user
        )

        assert run.triggered_from_ui is True
        assert run.triggered_by == triggering_user

    def test_passes_extra_kwargs_to_the_task(self):
        config = forwarding_config()

        run, _ = create_run_and_dispatch(
            config, 'some.task', start_over=True
        )

        mock_async().assert_called_once_with(
            'some.task', run.id, start_over=True
        )

    def test_enqueues_nothing_when_a_run_is_active(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            config=config, status=RunBaseModel.Status.STARTED
        )

        run, task_id = create_run_and_dispatch(config, 'some.task')

        assert run is None
        assert task_id is None
        mock_async().assert_not_called()
