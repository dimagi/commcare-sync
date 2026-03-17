from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0001_initial'),
        ('exports', '0021_remove_exportdatabase'),
        ('refreshes', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='refreshconfig',
                    name='database',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        help_text='PostgreSQL database connection',
                        to='db.Database',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
