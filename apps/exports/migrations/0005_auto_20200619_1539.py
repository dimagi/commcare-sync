# Generated by Django 3.0.5 on 2020-06-19 13:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exports', '0004_auto_20200617_0944'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exportdatabase',
            name='connection_string',
            field=models.CharField(max_length=500),
        ),
    ]
