# Generated by Django 3.2.18 on 2023-04-21 18:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0031_auto_20230420_2208"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activation",
            name="decision_environment",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.decisionenvironment",
            ),
        ),
    ]
