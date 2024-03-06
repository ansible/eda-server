# Generated by Django 4.2.7 on 2024-03-06 15:22

import django.db.models.deletion
from django.db import migrations, models

import aap_eda.core.utils.crypto.fields

PERMISSIONS = {
    "credential_type": ["create", "read", "update", "delete"],
    "eda_credential": ["create", "read", "update", "delete"],
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
        ("core", "0026_activation_log_level_eventstream_log_level"),
    ]

    operations = [
        migrations.CreateModel(
            name="CredentialType",
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
                ("description", models.TextField(blank=True, default="")),
                ("inputs", models.JSONField(default=dict)),
                ("injectors", models.JSONField(default=dict)),
                ("managed", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "core_credential_type",
            },
        ),
        migrations.AlterField(
            model_name="permission",
            name="resource_type",
            field=models.TextField(
                choices=[
                    ("activation", "activation"),
                    ("activation_instance", "activation_instance"),
                    ("audit_rule", "audit_rule"),
                    ("audit_event", "audit_event"),
                    ("user", "user"),
                    ("project", "project"),
                    ("extra_var", "extra_var"),
                    ("rulebook", "rulebook"),
                    ("role", "role"),
                    ("decision_environment", "decision_environment"),
                    ("credential", "credential"),
                    ("credential_type", "credential_type"),
                    ("eda_credential", "eda_credential"),
                    ("event_stream", "event_stream"),
                ]
            ),
        ),
        migrations.CreateModel(
            name="EdaCredential",
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
                ("description", models.TextField(blank=True, default="")),
                (
                    "inputs",
                    aap_eda.core.utils.crypto.fields.EncryptedTextField(
                        blank=True, default=""
                    ),
                ),
                ("managed", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                (
                    "credential_type",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.credentialtype",
                    ),
                ),
            ],
            options={
                "db_table": "core_eda_credential",
            },
        ),
        migrations.AddConstraint(
            model_name="credentialtype",
            constraint=models.CheckConstraint(
                check=models.Q(("name", ""), _negated=True),
                name="ck_empty_credential_type_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="edacredential",
            constraint=models.CheckConstraint(
                check=models.Q(("name", ""), _negated=True),
                name="ck_empty_eda_credential_name",
            ),
        ),
        migrations.RunPython(insert_permissions, drop_permissions),
    ]
