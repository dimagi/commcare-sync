from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('exports', '0020_encrypt_existing_connection_strings'),
        ('forwarding', '0001_initial'),
        ('refreshes', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Database',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('name', models.CharField(max_length=100)),
                        ('connection_string_encrypted', models.CharField(max_length=1000)),
                        ('owner', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            to=settings.AUTH_USER_MODEL,
                        )),
                    ],
                    options={
                        'abstract': False,
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "exports_exportdatabase" RENAME TO "db_database"',
                    reverse_sql='ALTER TABLE "db_database" RENAME TO "exports_exportdatabase"',
                ),
            ],
        ),
    ]
