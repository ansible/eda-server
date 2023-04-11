from django.db import migrations

PERMISSIONS = {
    "activation": [
        "create",
        "read",
        "update",
        "delete",
        "enable",
        "disable",
        "restart",
    ],
    "activation_instance": ["read", "delete"],
    "audit_rule": ["read"],
    "audit_event": ["read"],
    "task": ["read"],
    "user": ["create", "read", "update", "delete"],
    "project": ["create", "read", "update", "delete"],
    "inventory": ["create", "read", "update", "delete"],
    "extra_var": ["create", "read", "update", "delete"],
    "playbook": ["create", "read", "update", "delete"],
    "rulebook": ["create", "read", "update", "delete"],
    "role": ["create", "read", "update", "delete"],
    "decision_environment": ["create", "read", "update", "delete"],
    "credential": ["create", "read", "update", "delete"],
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
            resource_type=resource_type, actions__in=actions
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_reverse_role_users"),
    ]

    operations = [migrations.RunPython(insert_permissions, drop_permissions)]
