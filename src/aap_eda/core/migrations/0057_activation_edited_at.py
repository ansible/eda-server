# Generated by Django 4.2.16 on 2025-01-23 19:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0056_alter_activation_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="activation",
            name="edited_at",
            field=models.DateTimeField(null=True),
        ),
    ]
