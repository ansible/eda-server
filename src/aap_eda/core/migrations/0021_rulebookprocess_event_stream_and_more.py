# Generated by Django 4.2.7 on 2024-02-07 14:13

import django.db.models.deletion
from django.db import migrations, models

import aap_eda.core.enums


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0020_eventstream"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookprocess",
            name="event_stream",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="event_stream_processes",
                to="core.eventstream",
            ),
        ),
        migrations.AddField(
            model_name="rulebookprocess",
            name="parent_type",
            field=models.TextField(
                choices=[
                    ("activation", "activation"),
                    ("event_stream", "event_stream"),
                ],
                default=aap_eda.core.enums.ProcessParentType["ACTIVATION"],
            ),
        ),
        migrations.AlterField(
            model_name="rulebookprocess",
            name="activation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="activation_processes",
                to="core.activation",
            ),
        ),
    ]