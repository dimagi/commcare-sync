import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='Schedule',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'schedule_type',
                    models.CharField(
                        choices=[
                            ('interval', 'Every N minutes/hours/days'),
                            ('weekly', 'Weekly on specific days'),
                            ('monthly', 'Monthly on specific day'),
                            ('quarterly', 'Quarterly'),
                            (
                                'semi-annually',
                                'Semi-annually (twice per year)',
                            ),
                            ('annually', 'Annually'),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    'first_run_date',
                    models.DateField(
                        blank=True,
                        help_text="Don't run before this date",
                        null=True,
                    ),
                ),
                (
                    'first_run_time',
                    models.TimeField(
                        default='00:00',
                        help_text='Time of day for first/recurring runs',
                    ),
                ),
                (
                    'timezone',
                    models.CharField(
                        default='UTC',
                        help_text='Timezone for scheduled runs (e.g., '
                        "'America/New_York', 'UTC')",
                        max_length=63,
                    ),
                ),
                (
                    'interval_value',
                    models.PositiveIntegerField(
                        blank=True,
                        help_text='Number of time units between runs',
                        null=True,
                    ),
                ),
                (
                    'interval_unit',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('minutes', 'Minutes'),
                            ('hours', 'Hours'),
                            ('days', 'Days'),
                        ],
                        help_text='Time unit for interval',
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    'days_of_week',
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text='List of day numbers: 0=Sunday, 1=Monday, '
                        '..., 6=Saturday',
                    ),
                ),
                (
                    'periodic_task',
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='schedule',
                        to='django_celery_beat.periodictask',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
