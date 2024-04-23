# Generated by Django 4.2.7 on 2024-01-31 18:44

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import aap_eda.core.enums
import aap_eda.core.models.mixins

# The source of truth for permissions data changed since this migration
# - actions available for model is defined in model Meta properties
# - models tracked by role permissions added to permission_registry.register()
PERMISSIONS = {
    "event_stream": ["create", "read"],
}


def insert_permissions(apps, schema_editor):
    permission_model = apps.get_model("core", "Permission")
    db_alias = schema_editor.connection.alias
    permissions = []
    for resource_type, actions in PERMISSIONS.items():
        for action in actions:
            permissions.append(
                permission_model(resource_type=resource_type, action=action)
            )
    permission_model.objects.using(db_alias).bulk_create(permissions)


def drop_permissions(apps, schema_editor):
    permission_model = apps.get_model("core", "Permission")  # noqa: N806
    db_alias = schema_editor.connection.alias
    for resource_type, actions in PERMISSIONS.items():
        permission_model.objects.using(db_alias).filter(
            resource_type=resource_type, action__in=actions
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "core",
            "0019_activation_credentials_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="EventStream",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.TextField(unique=True)),
                ("description", models.TextField(default="")),
                ("is_enabled", models.BooleanField(default=True)),
                (
                    "restart_policy",
                    models.TextField(
                        choices=[
                            ("always", "always"),
                            ("on-failure", "on-failure"),
                            ("never", "never"),
                        ],
                        default=aap_eda.core.enums.RestartPolicy["ON_FAILURE"],
                    ),
                ),
                (
                    "status",
                    models.TextField(
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
                        ],
                        default=aap_eda.core.enums.ActivationStatus["PENDING"],
                    ),
                ),
                ("current_job_id", models.TextField(null=True)),
                ("restart_count", models.IntegerField(default=0)),
                ("failure_count", models.IntegerField(default=0)),
                (
                    "rulebook_name",
                    models.TextField(
                        default="", help_text="Name of the referenced rulebook"
                    ),
                ),
                (
                    "rulebook_rulesets",
                    models.TextField(
                        default="",
                        help_text="Content of the last referenced rulebook",
                    ),
                ),
                ("ruleset_stats", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("status_updated_at", models.DateTimeField(null=True)),
                ("status_message", models.TextField(default=None, null=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4)),
                ("source_type", models.TextField()),
                ("args", models.JSONField(default=None, null=True)),
                ("listener_args", models.JSONField(default=None, null=True)),
                (
                    "decision_environment",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.decisionenvironment",
                    ),
                ),
                (
                    "extra_var",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.extravar",
                    ),
                ),
                (
                    "latest_instance",
                    models.OneToOneField(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.rulebookprocess",
                    ),
                ),
                (
                    "rulebook",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.rulebook",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "core_event_stream",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["name"], name="ix_event_stream_name")
                ],
            },
            bases=(
                aap_eda.core.models.mixins.StatusHandlerModelMixin,
                models.Model,
            ),
        ),
        migrations.RunPython(insert_permissions, drop_permissions),
    ]
