import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_rulebook_path"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Role",
        ),
        migrations.DeleteModel(
            name="RolePermission",
        ),
        migrations.DeleteModel(
            name="UserRole",
        ),
        migrations.CreateModel(
            name="Permission",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                (
                    "resource_type",
                    models.TextField(
                        choices=[
                            ("activation", "activation"),
                            ("activation_instance", "activation_instance"),
                            ("audit_rule", "audit_rule"),
                            ("job", "job"),
                            ("task", "task"),
                            ("user", "user"),
                            ("project", "project"),
                            ("inventory", "inventory"),
                            ("extra_var", "extra_var"),
                            ("playbook", "playbook"),
                            ("rulebook", "rulebook"),
                            ("execution_env", "execution_env"),
                            ("role", "role"),
                        ]
                    ),
                ),
                (
                    "action",
                    models.TextField(
                        choices=[
                            ("create", "create"),
                            ("read", "read"),
                            ("update", "update"),
                            ("delete", "delete"),
                        ]
                    ),
                ),
            ],
            options={
                "db_table": "core_permission",
                "unique_together": {("resource_type", "action")},
            },
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.TextField(unique=True)),
                ("description", models.TextField(default="")),
                ("is_default", models.BooleanField(default=False, null=True)),
                (
                    "permissions",
                    models.ManyToManyField(
                        related_name="roles", to="core.Permission"
                    ),
                ),
                (
                    "users",
                    models.ManyToManyField(
                        related_name="roles", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "db_table": "core_role",
            },
        ),
    ]
