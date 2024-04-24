from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0035_remove_role_permissions_remove_user_roles_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="name",
            field=models.TextField(unique=True),
        ),
    ]
