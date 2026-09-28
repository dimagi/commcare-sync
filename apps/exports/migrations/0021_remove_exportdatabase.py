from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0001_initial'),
        ('exports', '0020_encrypt_existing_connection_strings'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='exportconfig',
                    name='database',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='db.Database',
                    ),
                ),
                migrations.AlterField(
                    model_name='multiprojectexportconfig',
                    name='database',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='db.Database',
                    ),
                ),
                migrations.DeleteModel(
                    name='ExportDatabase',
                ),
            ],
            database_operations=[],
        ),
    ]
