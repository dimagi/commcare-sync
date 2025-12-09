import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('exports', '0018_auto_20210219_1943'),
        ('forwarding', '0003_change_schedule_to_onetoone_remove_is_paused'),
    ]

    operations = [
        migrations.AlterField(
            model_name='forwardingconfig',
            name='database',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='exports.exportdatabase',
            ),
        ),
        migrations.DeleteModel(
            name='ForwardingDatabase',
        ),
    ]
