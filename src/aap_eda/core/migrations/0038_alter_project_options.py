from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0037_alter_activation_extra_var_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="project",
            options={"permissions": [("sync_project", "Can sync a project")]},
        ),
    ]
