from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exports', '0018_auto_20210219_1943'),
    ]

    operations = [
        migrations.RenameField(
            model_name='exportdatabase',
            old_name='connection_string',
            new_name='connection_string_encrypted',
        ),
        migrations.AlterField(
            model_name='exportdatabase',
            name='connection_string_encrypted',
            field=models.CharField(max_length=1000),
        ),
    ]
