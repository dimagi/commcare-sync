from django_q.brokers import get_broker
from django_q.models import OrmQ, Schedule
from unmagic import fixture, use

from apps.schedules.maintenance import (
    DISPATCHER_FUNC,
    DISPATCHER_MINUTES,
    DISPATCHER_NAME,
    clear_stale_queue_locks,
    ensure_dispatcher_schedule,
)

_caplog = fixture('caplog')


@use('db')
class TestEnsureDispatcherSchedule:
    def test_the_migration_already_created_it(self):
        assert ensure_dispatcher_schedule() is False
        [schedule] = Schedule.objects.filter(func=DISPATCHER_FUNC)
        # The migration keeps its own literals; they must agree.
        assert schedule.name == DISPATCHER_NAME
        assert schedule.schedule_type == Schedule.MINUTES
        assert schedule.minutes == DISPATCHER_MINUTES

    def test_recreates_a_deleted_schedule(self):
        Schedule.objects.filter(func=DISPATCHER_FUNC).delete()

        assert ensure_dispatcher_schedule() is True

        schedule = Schedule.objects.get(func=DISPATCHER_FUNC)
        assert schedule.schedule_type == Schedule.MINUTES
        assert schedule.minutes == 1

    def test_tolerates_a_duplicated_schedule(self):
        Schedule.objects.create(
            func=DISPATCHER_FUNC, schedule_type=Schedule.MINUTES, minutes=5
        )

        assert ensure_dispatcher_schedule() is False

        assert Schedule.objects.filter(func=DISPATCHER_FUNC).count() == 2


@use('db')
class TestClearStaleQueueLocks:
    @use(_caplog)
    def test_a_locked_task_becomes_deliverable_again(self):
        broker = get_broker()
        broker.enqueue('payload')
        broker.dequeue()
        assert broker.queue_size() == 0

        with _caplog().at_level('WARNING'):
            assert clear_stale_queue_locks() == 1

        assert broker.queue_size() == 1
        # A repair of a crash's leftovers is worth a line in app.log.
        assert 'Cleared 1 stale task queue lock' in _caplog().text

    def test_a_deliverable_task_is_left_alone(self):
        broker = get_broker()
        broker.enqueue('payload')

        assert clear_stale_queue_locks() == 0

    def test_an_empty_queue(self):
        assert OrmQ.objects.count() == 0
        assert clear_stale_queue_locks() == 0
