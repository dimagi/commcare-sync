# Generated by Django 3.0.5 on 2020-07-21 08:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commcare', '0005_auto_20200514_1153'),
        ('exports', '0008_auto_20200721_1035'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='MultiProjectExportRun',
            new_name='MultiProjectPartialExportRun',
        ),
        # rename the index to workaround this bug https://code.djangoproject.com/ticket/23577#comment:17
        migrations.RunSQL(
            'ALTER INDEX exports_multiprojectexportrun_export_config_id_bcc53671 rename TO exports_multiprojectpartialexportrun_export_config_id_bcc53671myapp_mymodel_myfield_othermodel_id_0f4cfc54',
        ),
    ]
