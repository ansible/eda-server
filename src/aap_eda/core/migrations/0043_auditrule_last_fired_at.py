# Generated by Django 3.2.18 on 2023-05-30 22:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0042_activationinstance_activation_pod_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditrule",
            name="last_fired_at",
            field=models.DateTimeField(null=True),
        ),
    ]
