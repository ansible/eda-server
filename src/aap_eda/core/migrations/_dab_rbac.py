import logging

from ansible_base.rbac.management import create_dab_permissions
from ansible_base.rbac.migrations._utils import give_permissions
from django.apps import apps as global_apps
from django.conf import settings
from django.utils.timezone import now

logger = logging.getLogger("aap_eda.core.migrations._dab_rbac")


def create_permissions_as_operation(apps, schema_editor):
    create_dab_permissions(global_apps.get_app_config("core"), apps=apps)


# this maps action names from prior permission model to the Django names
# these are also required to generally match DAB RBAC expections
action_mapping = {"create": "add", "read": "view", "update": "change"}


def migrate_roles_to_dab(apps, schema_editor):
    Role = apps.get_model("core", "Role")  # noqa: N806
    RoleDefinition = apps.get_model("dab_rbac", "RoleDefinition")  # noqa: N806
    Organization = apps.get_model("core", "Organization")  # noqa: N806
    ContentType = apps.get_model("contenttypes", "ContentType")  # noqa: N806
    DABPermission = apps.get_model("dab_rbac", "DABPermission")  # noqa: N806

    default_org = Organization.objects.get(
        name=settings.DEFAULT_ORGANIZATION_NAME
    )
    org_ct = ContentType.objects.get_for_model(Organization)
    migration_now = now()

    for role in Role.objects.all():
        logger.info(f"Migrating role {role.name} to new system")

        new_permissions = []
        for p in role.permissions.all():
            action = action_mapping.get(p.action, p.action)
            model_name = p.resource_type.replace("_", "")
            if model_name == "activationinstance":
                model_name = "rulebookprocess"
            if model_name in ("user", "role"):
                continue  # org-level roles need new rules for these
            elif model_name in ("playbook", "inventory", "task"):
                continue  # models were removed

            ct = ContentType.objects.get(model=model_name)
            permission = DABPermission.objects.get(
                content_type=ct, codename__startswith=action
            )
            new_permissions.append(permission)

        # Role in new system is created as an organization-level role
        new_role, _ = RoleDefinition.objects.get_or_create(
            name=role.name,
            defaults={
                "description": role.description,
                "content_type": org_ct,
                "created": migration_now,
                "modified": migration_now,
            },
        )
        new_role.permissions.add(*new_permissions)
        logger.debug(f"Created new role {new_role.name} id={new_role.id}")

        # Permissions are all applied to the default organization
        user_ct = role.users.count()
        if role.users.count():
            logger.info(
                f"Migrating {user_ct} memberships of {role.name} role to new role system"
            )
            give_permissions(
                apps,
                new_role,
                users=role.users.all(),
                object_id=default_org.id,
                content_type_id=org_ct.id,
            )


def remove_dab_models(apps, schema_editor):
    apps.get_model("dab_rbac", "RoleUserAssignment").objects.all().delete()
    apps.get_model("dab_rbac", "RoleTeamAssignment").objects.all().delete()
    apps.get_model("dab_rbac", "ObjectRole").objects.all().delete()
    apps.get_model("dab_rbac", "RoleDefinition").objects.all().delete()
