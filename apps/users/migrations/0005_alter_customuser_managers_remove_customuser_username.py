from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_alter_customuser_email"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="customuser",
            managers=[],
        ),
        migrations.RunSQL(
            sql=[
                "ALTER TABLE users_customuser DROP COLUMN username",
            ],
            reverse_sql=[
                "ALTER TABLE users_customuser ADD COLUMN username varchar(150)",
                "UPDATE users_customuser SET username = email",
                "ALTER TABLE users_customuser ALTER COLUMN username SET NOT NULL",
                "ALTER TABLE users_customuser ADD CONSTRAINT users_customuser_username_key UNIQUE (username)",
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="customuser",
                    name="username",
                ),
            ],
        ),
    ]
