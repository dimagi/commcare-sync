"""
Tests for migration 0025: migrate_export_schedules.

The migration functions use `apps.get_model()` which returns historical model
classes during real migrations. We can't replicate that outside the migration
framework, so we test the equivalent SQL logic directly.
"""

import json

from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import connection
from django.db.models.signals import post_save, pre_delete
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from unmagic import fixture, use

from apps.exports.models import ExportConfig, MultiProjectExportConfig
from apps.schedules.signals import create_or_update_periodic_task, delete_periodic_task


TASK_MAPPING = {
    'exports_exportconfig': 'apps.exports.tasks.run_scheduled_export_task',
    'exports_multiprojectexportconfig': 'apps.exports.tasks.run_scheduled_multi_export_task',
}
PREFIX_MAPPING = {
    'exports_exportconfig': 'Run export',
    'exports_multiprojectexportconfig': 'Run multi-project export',
}


def _disconnect_export_signals():
    post_save.disconnect(create_or_update_periodic_task, sender=ExportConfig)
    pre_delete.disconnect(delete_periodic_task, sender=ExportConfig)
    post_save.disconnect(create_or_update_periodic_task, sender=MultiProjectExportConfig)
    pre_delete.disconnect(delete_periodic_task, sender=MultiProjectExportConfig)


def _reconnect_export_signals():
    post_save.connect(create_or_update_periodic_task, sender=ExportConfig)
    pre_delete.connect(delete_periodic_task, sender=ExportConfig)
    post_save.connect(create_or_update_periodic_task, sender=MultiProjectExportConfig)
    pre_delete.connect(delete_periodic_task, sender=MultiProjectExportConfig)


@use('db')
@fixture
def migration_test_fixture():
    """Set up legacy columns, disconnect signals, clean up after."""
    _disconnect_export_signals()
    with connection.cursor() as cursor:
        for table in ('exports_exportconfig', 'exports_multiprojectexportconfig'):
            cursor.execute(
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS '
                f'time_between_runs integer NOT NULL DEFAULT 720'
            )
            cursor.execute(
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS '
                f'is_paused boolean NOT NULL DEFAULT false'
            )
    yield
    # No need to drop legacy columns — the test framework rolls back the
    # transaction, undoing both the column additions and all test data.
    _reconnect_export_signals()


def _create_export_with_legacy_fields(*, time_between_runs, is_paused):
    """Create an ExportConfig with legacy field values set via raw SQL."""
    from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
    from apps.db.models import Database
    from django.contrib.auth import get_user_model

    User = get_user_model()
    server, _ = CommCareServer.objects.get_or_create(
        url=settings.COMMCARE_DEFAULT_SERVER
    )
    project, _ = CommCareProject.objects.get_or_create(
        server=server, domain='migration-test'
    )
    user, _ = User.objects.get_or_create(
        username='migration-test', defaults={'email': 'test@test.com'}
    )
    account, _ = CommCareAccount.objects.get_or_create(
        server=server, username='migration-test',
        defaults={'api_key': 'test', 'owner': user},
    )
    database, _ = Database.objects.get_or_create(
        name='migration-test-db',
        defaults={'connection_string': 'postgresql://x:x@localhost/test'},
    )
    config_file = TemporaryUploadedFile(
        name='test.xlsx', content_type='application/xml', size=10, charset='utf-8',
    )
    export = ExportConfig.objects.create(
        name=f'test-tbr{time_between_runs}-paused{is_paused}',
        project=project,
        account=account,
        database=database,
        config_file=config_file,
        extra_args='',
    )
    config_file.close()

    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE exports_exportconfig '
            'SET time_between_runs = %s, is_paused = %s, '
            '    schedule_type = NULL, interval_value = NULL, '
            '    interval_unit = NULL, periodic_task_id = NULL '
            'WHERE id = %s',
            [time_between_runs, is_paused, export.id],
        )
    return export.id


def _run_forward_migration(table='exports_exportconfig'):
    """Replicate migrate_export_schedules logic using raw SQL reads."""
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT id, time_between_runs, is_paused FROM {table}'
        )
        for export_id, tbr, paused in cursor.fetchall():
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=tbr, period='minutes',
            )
            task_name = f'{PREFIX_MAPPING[table]}: ID {export_id}'
            periodic_task = PeriodicTask.objects.create(
                task=TASK_MAPPING[table],
                name=task_name,
                enabled=not paused,
                args=json.dumps([export_id]),
                interval=schedule,
            )
            cursor.execute(
                f'UPDATE {table} SET schedule_type = %s, interval_value = %s, '
                f'interval_unit = %s, periodic_task_id = %s WHERE id = %s',
                ['interval', tbr, 'minutes', periodic_task.id, export_id],
            )


def _run_reverse_migration(table='exports_exportconfig'):
    """Replicate reverse_migrate logic using raw SQL reads."""
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT id, schedule_type, interval_value, periodic_task_id FROM {table}'
        )
        for export_id, schedule_type, interval_value, pt_id in cursor.fetchall():
            tbr = interval_value if schedule_type == 'interval' else 720
            paused = True
            if pt_id:
                pt = PeriodicTask.objects.filter(id=pt_id).first()
                if pt:
                    paused = not pt.enabled
                    pt.delete()
            cursor.execute(
                f'UPDATE {table} SET time_between_runs = %s, is_paused = %s, '
                f'periodic_task_id = NULL WHERE id = %s',
                [tbr, paused, export_id],
            )


@migration_test_fixture
def test_forward_migration_active_export():
    """Active exports get schedule fields AND an enabled PeriodicTask."""
    migration_test_fixture()
    export_id = _create_export_with_legacy_fields(
        time_between_runs=30, is_paused=False,
    )

    _run_forward_migration()

    export = ExportConfig.objects.get(id=export_id)
    assert export.schedule_type == 'interval'
    assert export.interval_value == 30
    assert export.interval_unit == 'minutes'
    assert export.periodic_task is not None
    assert export.periodic_task.enabled is True
    assert export.periodic_task.task == 'apps.exports.tasks.run_scheduled_export_task'
    assert json.loads(export.periodic_task.args) == [export_id]


@migration_test_fixture
def test_forward_migration_paused_export():
    """Paused exports get schedule fields AND a DISABLED PeriodicTask."""
    migration_test_fixture()
    export_id = _create_export_with_legacy_fields(
        time_between_runs=60, is_paused=True,
    )

    _run_forward_migration()

    export = ExportConfig.objects.get(id=export_id)
    assert export.schedule_type == 'interval'
    assert export.interval_value == 60
    assert export.interval_unit == 'minutes'
    assert export.periodic_task is not None
    assert export.periodic_task.enabled is False


@migration_test_fixture
def test_reverse_migration_restores_paused_state():
    """Reverse migration restores is_paused=True for paused exports."""
    migration_test_fixture()
    export_id = _create_export_with_legacy_fields(
        time_between_runs=45, is_paused=True,
    )

    _run_forward_migration()
    _run_reverse_migration()

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT is_paused, time_between_runs '
            'FROM exports_exportconfig WHERE id = %s',
            [export_id],
        )
        is_paused, tbr = cursor.fetchone()
    assert is_paused is True
    assert tbr == 45

    export = ExportConfig.objects.get(id=export_id)
    assert export.periodic_task is None


@migration_test_fixture
def test_reverse_migration_restores_active_state():
    """Reverse migration sets is_paused=False for active exports."""
    migration_test_fixture()
    export_id = _create_export_with_legacy_fields(
        time_between_runs=30, is_paused=False,
    )

    _run_forward_migration()
    _run_reverse_migration()

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT is_paused, time_between_runs '
            'FROM exports_exportconfig WHERE id = %s',
            [export_id],
        )
        is_paused, tbr = cursor.fetchone()
    assert is_paused is False
    assert tbr == 30

    export = ExportConfig.objects.get(id=export_id)
    assert export.periodic_task is None
