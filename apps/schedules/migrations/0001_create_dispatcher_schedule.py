from django.db import migrations


def create_dispatcher_schedule(apps, schema_editor):
    Schedule = apps.get_model('django_q', 'Schedule')
    Schedule.objects.get_or_create(
        func='apps.schedules.tasks.run_due_schedules',
        defaults={
            'name': 'Run due schedules',
            'schedule_type': 'I',  # Schedule.MINUTES
            'minutes': 1,
        },
    )


def delete_dispatcher_schedule(apps, schema_editor):
    Schedule = apps.get_model('django_q', 'Schedule')
    Schedule.objects.filter(
        func='apps.schedules.tasks.run_due_schedules'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('django_q', '__first__'),
    ]

    operations = [
        migrations.RunPython(
            create_dispatcher_schedule,
            delete_dispatcher_schedule,
        ),
    ]
