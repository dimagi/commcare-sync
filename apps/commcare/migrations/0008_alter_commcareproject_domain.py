import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commcare', '0007_encrypt_existing_api_keys'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcareproject',
            name='domain',
            field=models.CharField(
                help_text='Your CommCare domain (available from the URL)',
                max_length=100,
                validators=[
                    django.core.validators.RegexValidator(
                        message=(
                            'Enter a valid CommCare domain: lowercase letters '
                            'and numbers, with single hyphens between them.'
                        ),
                        regex='^[a-z0-9]+(?:-[a-z0-9]+)*$',
                    )
                ],
            ),
        ),
    ]
