import json

from django.db import migrations

TASK_MAPPING = {
    'ExportConfig': 'apps.exports.tasks.run_scheduled_export_task',
    'MultiProjectExportConfig': 'apps.exports.tasks.run_scheduled_multi_export_task',
}
PREFIX_MAPPING = {
    'ExportConfig': 'Run export',
    'MultiProjectExportConfig': 'Run multi-project export',
}


def migrate_export_schedules(apps, schema_editor):
    """Convert time_between_runs + is_paused to ScheduleMixin fields and create PeriodicTasks."""
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    for model_name in ('ExportConfig', 'MultiProjectExportConfig'):
        Model = apps.get_model('exports', model_name)
        for export in Model.objects.all():
            export.schedule_type = 'interval'
            export.interval_value = export.time_between_runs
            export.interval_unit = 'minutes'

            # Create IntervalSchedule
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=export.time_between_runs,
                period='minutes',
            )

            # Create PeriodicTask (disabled if export was paused)
            task_name = (
                f'{PREFIX_MAPPING[model_name]}: {export} (ID: {export.id})'
            )
            periodic_task = PeriodicTask.objects.create(
                task=TASK_MAPPING[model_name],
                name=task_name,
                enabled=not export.is_paused,
                args=json.dumps([export.id]),
                interval=schedule,
            )
            export.periodic_task = periodic_task
            export.save(
                update_fields=[
                    'schedule_type',
                    'interval_value',
                    'interval_unit',
                    'periodic_task',
                ]
            )


def reverse_migrate(apps, schema_editor):
    """Convert ScheduleMixin fields back to time_between_runs + is_paused."""
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    for model_name in ('ExportConfig', 'MultiProjectExportConfig'):
        Model = apps.get_model('exports', model_name)
        for export in Model.objects.all():
            if export.schedule_type == 'interval':
                export.time_between_runs = export.interval_value
            # Derive is_paused from periodic_task.enabled
            if export.periodic_task_id:
                pt = PeriodicTask.objects.filter(
                    id=export.periodic_task_id
                ).first()
                export.is_paused = not pt.enabled if pt else True
                if pt:
                    pt.delete()
                export.periodic_task = None
            else:
                export.is_paused = True

            export.save(
                update_fields=[
                    'is_paused',
                    'time_between_runs',
                    'periodic_task',
                ]
            )


class Migration(migrations.Migration):
    dependencies = [
        ('exports', '0024_exportconfig_days_of_week_and_more'),
        ('django_celery_beat', '__latest__'),
    ]

    operations = [
        migrations.RunPython(migrate_export_schedules, reverse_migrate),
    ]
