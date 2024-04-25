# Generated by Django 4.2.7 on 2024-02-08 18:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        (
            "core",
            "0031_alter_activation_status_alter_eventstream_status_and_more",
        ),
    ]
    run_before = [("dab_rbac", "__first__")]

    operations = [
        migrations.CreateModel(
            name="Organization",
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
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="The date/time this resource was created",
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="The date/time this resource was created",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="The name of this resource",
                        max_length=512,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="The organization description.",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        default=None,
                        editable=False,
                        help_text="The user who created this resource",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_created+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        default=None,
                        editable=False,
                        help_text="The user who last modified this resource",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_modified+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Team",
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
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="The date/time this resource was created",
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="The date/time this resource was created",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="The name of this resource", max_length=512
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="The team description.",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        default=None,
                        editable=False,
                        help_text="The user who created this resource",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_created+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        default=None,
                        editable=False,
                        help_text="The user who last modified this resource",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_modified+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        help_text="The organization of this team.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teams",
                        to="core.organization",
                    ),
                ),
            ],
            options={
                "ordering": ("organization__name", "name"),
                "abstract": False,
                "unique_together": {("organization", "name")},
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
                    ("organization", "organization"),
                    ("team", "team"),
                ]
            ),
        ),
    ]
