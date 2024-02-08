from django.conf import settings
from django.db import migrations
from django.utils import timezone


def create_default_org(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")  # noqa: N806

    db_alias = schema_editor.connection.alias

    now = timezone.now()
    Organization.objects.using(db_alias).get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
        created_on=now,
        modified_on=now,
    )


def delete_default_org(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")  # noqa: N806
    db_alias = schema_editor.connection.alias

    Organization.objects.using(db_alias).filter(
        name=settings.DEFAULT_ORGANIZATION_NAME
    ).delete()


def add_resources_to_default_org(apps, schema_editor):
    resources_list = (
        "Activation",
        "AuditAction",
        "AuditEvent",
        "AuditRule",
        "Credential",
        "DecisionEnvironment",
        "ExtraVar",
        "Project",
        "Role",
        "Rulebook",
        "RulebookProcess",
        "RulebookProcessLog",
        "User",
    )

    Organization = apps.get_model("core", "Organization")  # noqa: N806
    db_alias = schema_editor.connection.alias

    default_org = (
        Organization.objects.using(db_alias)
        .filter(name=settings.DEFAULT_ORGANIZATION_NAME)
        .first()
    )

    for resource in resources_list:
        resource_model = apps.get_model("core", resource)
        for obj in resource_model.objects.all():
            if obj.organization is None:
                obj.organization = default_org
                obj.save(update_fields=["organization"])


def remove_resources_from_default_org(apps, schema_editor):
    resources_list = (
        "Activation",
        "AuditAction",
        "AuditEvent",
        "AuditRule",
        "Credential",
        "DecisionEnvironment",
        "ExtraVar",
        "Project",
        "Role",
        "Rulebook",
        "RulebookProcess",
        "RulebookProcessLog",
        "User",
    )

    Organization = apps.get_model("core", "Organization")  # noqa: N806
    db_alias = schema_editor.connection.alias

    default_org = (
        Organization.objects.using(db_alias)
        .filter(name=settings.DEFAULT_ORGANIZATION_NAME)
        .first()
    )

    for resource in resources_list:
        resource_model = apps.get_model("core", resource)
        for obj in resource_model.objects.all(
            organization=default_org
        ).iterator():
            obj.organization = None
            obj.save(update_fields=["organization"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "core",
            "0021_organization_team_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            code=create_default_org, reverse_code=delete_default_org
        ),
        migrations.RunPython(
            code=add_resources_to_default_org,
            reverse_code=remove_resources_from_default_org,
        ),
    ]
