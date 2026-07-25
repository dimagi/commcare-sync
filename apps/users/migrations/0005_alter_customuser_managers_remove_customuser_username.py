from django.db import migrations, models


def drop_username(apps, schema_editor):
    CustomUser = apps.get_model("users", "customuser")
    schema_editor.remove_field(CustomUser, CustomUser._meta.get_field("username"))


def restore_username(apps, schema_editor):
    CustomUser = apps.get_model("users", "customuser")
    nullable_field = models.CharField(max_length=150, null=True)
    nullable_field.set_attributes_from_name("username")
    schema_editor.add_field(CustomUser, nullable_field)

    CustomUser.objects.update(username=models.F("email"))

    required_unique_field = models.CharField(max_length=150, unique=True)
    required_unique_field.set_attributes_from_name("username")
    schema_editor.alter_field(CustomUser, nullable_field, required_unique_field)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_alter_customuser_email"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="customuser",
            managers=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="customuser",
                    name="username",
                ),
            ],
            database_operations=[
                migrations.RunPython(drop_username, restore_username),
            ],
        ),
    ]
