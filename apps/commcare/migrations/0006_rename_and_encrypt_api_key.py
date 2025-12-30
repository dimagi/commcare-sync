from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commcare', '0005_auto_20200514_1153'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcareaccount',
            old_name='api_key',
            new_name='api_key_encrypted',
        ),
        migrations.AlterField(
            model_name='commcareaccount',
            name='api_key_encrypted',
            field=models.CharField(
                help_text='Your API key is available under "My Account Settings" in CommCare.',
                max_length=255,
            ),
        ),
    ]
