# Generated by Django 3.2.18 on 2023-05-11 14:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0039_auto_20230508_1717"),
    ]

    operations = [
        migrations.AddField(
            model_name="activation",
            name="ruleset_stats",
            field=models.JSONField(default=dict),
        ),
    ]
