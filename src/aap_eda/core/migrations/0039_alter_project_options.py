from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0038_alter_activation_description_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="project",
            options={"permissions": [("sync_project", "Can sync a project")]},
        ),
    ]
