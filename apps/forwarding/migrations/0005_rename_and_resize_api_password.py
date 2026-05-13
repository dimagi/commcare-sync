from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forwarding', '0004_rename_triggering_user_forwardingrun_triggered_by_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='forwardingdestination',
            old_name='api_password',
            new_name='api_password_encrypted',
        ),
        migrations.AlterField(
            model_name='forwardingdestination',
            name='api_password_encrypted',
            field=models.CharField(
                blank=True,
                help_text='Password for basic authentication',
                max_length=500,
            ),
        ),
    ]
