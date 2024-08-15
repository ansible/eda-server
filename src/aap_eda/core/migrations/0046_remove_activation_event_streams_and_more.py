# Generated by Django 4.2.7 on 2024-08-15 14:04

from django.db import migrations, models

import aap_eda.core.enums


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0045_activation_skip_audit_events"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="activation",
            name="event_streams",
        ),
        migrations.RemoveField(
            model_name="rulebookprocess",
            name="event_stream",
        ),
        migrations.AlterField(
            model_name="activationrequestqueue",
            name="process_parent_type",
            field=models.TextField(
                choices=[("activation", "activation")],
                default=aap_eda.core.enums.ProcessParentType["ACTIVATION"],
            ),
        ),
        migrations.AlterField(
            model_name="rulebookprocess",
            name="parent_type",
            field=models.TextField(
                choices=[("activation", "activation")],
                default=aap_eda.core.enums.ProcessParentType["ACTIVATION"],
            ),
        ),
        migrations.DeleteModel(
            name="EventStream",
        ),
    ]
