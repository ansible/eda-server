import django.db.models.deletion
from django.db import migrations, models

import aap_eda.core.enums


def populate_rulebook_process_queue(apps, schema_editor):
    RulebookProcessQueue = apps.get_model(  # noqa: N806
        "core", "RulebookProcessQueue"
    )
    RulebookProcess = apps.get_model("core", "RulebookProcess")  # noqa: N806
    for running_process in RulebookProcess.objects.filter(
        status="RUNNING",
    ).all():
        RulebookProcessQueue.objects.create(
            queue_name="activation",
            process=running_process,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0030_activation_k8s_service_name_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activation",
            name="status",
            field=models.TextField(
                choices=[
                    ("starting", "starting"),
                    ("running", "running"),
                    ("pending", "pending"),
                    ("failed", "failed"),
                    ("stopping", "stopping"),
                    ("stopped", "stopped"),
                    ("deleting", "deleting"),
                    ("completed", "completed"),
                    ("unresponsive", "unresponsive"),
                    ("error", "error"),
                    ("workers offline", "workers offline"),
                ],
                default=aap_eda.core.enums.ActivationStatus["PENDING"],
            ),
        ),
        migrations.AlterField(
            model_name="eventstream",
            name="status",
            field=models.TextField(
                choices=[
                    ("starting", "starting"),
                    ("running", "running"),
                    ("pending", "pending"),
                    ("failed", "failed"),
                    ("stopping", "stopping"),
                    ("stopped", "stopped"),
                    ("deleting", "deleting"),
                    ("completed", "completed"),
                    ("unresponsive", "unresponsive"),
                    ("error", "error"),
                    ("workers offline", "workers offline"),
                ],
                default=aap_eda.core.enums.ActivationStatus["PENDING"],
            ),
        ),
        migrations.AlterField(
            model_name="rulebookprocess",
            name="status",
            field=models.TextField(
                choices=[
                    ("starting", "starting"),
                    ("running", "running"),
                    ("pending", "pending"),
                    ("failed", "failed"),
                    ("stopping", "stopping"),
                    ("stopped", "stopped"),
                    ("deleting", "deleting"),
                    ("completed", "completed"),
                    ("unresponsive", "unresponsive"),
                    ("error", "error"),
                    ("workers offline", "workers offline"),
                ],
                default=aap_eda.core.enums.ActivationStatus["PENDING"],
            ),
        ),
        migrations.CreateModel(
            name="RulebookProcessQueue",
            fields=[
                ("queue_name", models.CharField(max_length=255)),
                (
                    "process",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="core.rulebookprocess",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["queue_name"],
                        name="core_rulebo_queue_n_b7b007_idx",
                    )
                ],
            },
        ),
        migrations.RunPython(
            populate_rulebook_process_queue,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
