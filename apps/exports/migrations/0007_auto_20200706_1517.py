# Generated by Django 3.0.5 on 2020-07-06 13:17

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('exports', '0006_auto_20200622_1626'),
    ]

    operations = [
        migrations.AddField(
            model_name='exportconfig',
            name='time_between_runs',
            field=models.PositiveIntegerField(default=int(settings.COMMCARE_SYNC_EXPORT_PERIODICITY / 60), help_text='How regularly to sync this export, in minutes.'),
        ),
        migrations.AddField(
            model_name='multiprojectexportconfig',
            name='time_between_runs',
            field=models.PositiveIntegerField(default=int(settings.COMMCARE_SYNC_EXPORT_PERIODICITY / 60), help_text='How regularly to sync this export, in minutes.'),
        ),
        migrations.AlterField(
            model_name='exportconfig',
            name='is_paused',
            field=models.BooleanField(default=False, help_text='Pausing an export will disable automatic syncing. You can still manually run it.'),
        ),
        migrations.AlterField(
            model_name='multiprojectexportconfig',
            name='is_paused',
            field=models.BooleanField(default=False, help_text='Pausing an export will disable automatic syncing. You can still manually run it.'),
        ),
    ]
