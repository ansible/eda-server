# Generated by Django 4.2.7 on 2024-04-19 18:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0035_remove_role_permissions_remove_user_roles_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activation",
            name="extra_var",
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name="eventstream",
            name="extra_var",
            field=models.TextField(null=True),
        ),
        migrations.DeleteModel(
            name="ExtraVar",
        ),
    ]
