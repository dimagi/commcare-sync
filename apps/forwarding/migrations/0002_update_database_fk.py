from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0001_initial'),
        ('exports', '0021_remove_exportdatabase'),
        ('forwarding', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='forwardingconfig',
                    name='database',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='db.Database',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
