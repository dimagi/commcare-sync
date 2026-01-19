from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from apps.exports.models import ExportDatabase
from apps.schedules.models import Schedule

from ..models import ForwardingConfig, ForwardingDestination
from ..tasks import (
    delete_orphaned_periodic_tasks,
    ensure_periodic_tasks_exist,
    sync_forwarding_schedules,
)

User = get_user_model()


class ForwardingTasksTestBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass',
        )
        self.database = ExportDatabase.objects.create(
            name='Test DB',
            connection_string='postgresql://localhost/test',
            owner=self.user,
        )
        self.destination = ForwardingDestination.objects.create(
            name='Test API',
            api_url='https://example.com/api',
            owner=self.user,
        )
        self.interval = IntervalSchedule.objects.create(
            every=30, period=IntervalSchedule.MINUTES
        )


class TestEnsurePeriodicTasksExist(ForwardingTasksTestBase):

    def test_creates_periodic_task_when_missing(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )
        ForwardingConfig.objects.create(
            name='Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            schedule=schedule,
        )
        schedule.refresh_from_db()
        schedule.periodic_task.delete()
        schedule.periodic_task = None
        schedule.save()

        count = ensure_periodic_tasks_exist()

        schedule.refresh_from_db()
        assert schedule.periodic_task is not None
        assert count == 1

    def test_updates_existing_periodic_task(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )
        ForwardingConfig.objects.create(
            name='Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            schedule=schedule,
        )
        schedule.refresh_from_db()
        old_task_name = schedule.periodic_task.name
        schedule.periodic_task.name = 'Old Name'
        schedule.periodic_task.save()

        count = ensure_periodic_tasks_exist()

        schedule.refresh_from_db()
        assert schedule.periodic_task.name == old_task_name
        assert count == 1

    def test_handles_multiple_configs(self):
        schedule1 = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )
        schedule2 = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 0),
            days_of_week=[1, 3, 5],
        )
        ForwardingConfig.objects.create(
            name='Config 1',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            schedule=schedule1,
        )
        ForwardingConfig.objects.create(
            name='Config 2',
            database=self.database,
            destination=self.destination,
            query='SELECT 2',
            created_by=self.user,
            schedule=schedule2,
        )

        count = ensure_periodic_tasks_exist()

        assert count == 2
        schedule1.refresh_from_db()
        schedule2.refresh_from_db()
        assert schedule1.periodic_task is not None
        assert schedule2.periodic_task is not None

    def test_skips_configs_without_schedule(self):
        ForwardingConfig.objects.create(
            name='Unscheduled',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
        )

        count = ensure_periodic_tasks_exist()

        assert count == 0


class TestDeleteOrphanedPeriodicTasks(ForwardingTasksTestBase):

    def test_deletes_orphaned_periodic_task(self):
        orphaned_task = PeriodicTask.objects.create(
            task='apps.forwarding.tasks.run_scheduled_forwarding_task',
            name='Orphaned Task',
            args='[9999]',
            interval=self.interval,
        )

        count = delete_orphaned_periodic_tasks()

        assert not PeriodicTask.objects.filter(id=orphaned_task.id).exists()
        assert count == 1

    def test_ignores_task_with_invalid_args(self):
        invalid_task = PeriodicTask.objects.create(
            task='apps.forwarding.tasks.run_scheduled_forwarding_task',
            name='Invalid Task',
            args='invalid json',
            interval=self.interval,
        )

        count = delete_orphaned_periodic_tasks()

        assert PeriodicTask.objects.filter(id=invalid_task.id).exists()
        assert count == 0

    def test_deletes_multiple_orphaned_tasks(self):
        for i in range(3):
            PeriodicTask.objects.create(
                task='apps.forwarding.tasks.run_scheduled_forwarding_task',
                name=f'Orphaned Task {i}',
                args=f'[{9000 + i}]',
                interval=self.interval,
            )

        count = delete_orphaned_periodic_tasks()

        assert count == 3

    def test_preserves_non_orphaned_tasks(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )
        ForwardingConfig.objects.create(
            name='Active Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            schedule=schedule,
        )
        schedule.refresh_from_db()
        task_id = schedule.periodic_task.id

        count = delete_orphaned_periodic_tasks()

        assert PeriodicTask.objects.filter(id=task_id).exists()
        assert count == 0

    def test_handles_mixed_orphaned_and_active_tasks(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )
        ForwardingConfig.objects.create(
            name='Active',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            schedule=schedule,
        )
        PeriodicTask.objects.create(
            task='apps.forwarding.tasks.run_scheduled_forwarding_task',
            name='Orphaned Task',
            args='[9999]',
            interval=self.interval,
        )

        count = delete_orphaned_periodic_tasks()

        assert count == 1
        schedule.refresh_from_db()
        assert schedule.periodic_task is not None


class TestSyncForwardingSchedules(ForwardingTasksTestBase):

    def test_calls_both_functions(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )
        ForwardingConfig.objects.create(
            name='Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            schedule=schedule,
        )
        PeriodicTask.objects.create(
            task='apps.forwarding.tasks.run_scheduled_forwarding_task',
            name='Orphaned Task',
            args='[9999]',
            interval=self.interval,
        )

        result = sync_forwarding_schedules()

        assert result['synced'] == 1
        assert result['orphaned_deleted'] == 1
