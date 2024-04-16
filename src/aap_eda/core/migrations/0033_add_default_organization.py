from django.conf import settings
from django.db import migrations
from django.utils import timezone

RESOURCES_LIST = (
    "Activation",
    "CredentialType",
    "EdaCredential",
    "DecisionEnvironment",
    "ExtraVar",
    "Project",
)


def create_default_org(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")  # noqa: N806

    db_alias = schema_editor.connection.alias

    now = timezone.now()
    Organization.objects.using(db_alias).get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
        created=now,
        modified=now,
    )


def delete_default_org(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")  # noqa: N806
    db_alias = schema_editor.connection.alias

    Organization.objects.using(db_alias).filter(
        name=settings.DEFAULT_ORGANIZATION_NAME
    ).delete()


def add_resources_to_default_org(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")  # noqa: N806
    db_alias = schema_editor.connection.alias

    default_org = (
        Organization.objects.using(db_alias)
        .filter(name=settings.DEFAULT_ORGANIZATION_NAME)
        .first()
    )

    for resource in RESOURCES_LIST:
        resource_model = apps.get_model("core", resource)
        resource_model.objects.update(organization=default_org)


def remove_resources_from_default_org(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")  # noqa: N806
    db_alias = schema_editor.connection.alias

    default_org = (
        Organization.objects.using(db_alias)
        .filter(name=settings.DEFAULT_ORGANIZATION_NAME)
        .first()
    )

    for resource in RESOURCES_LIST:
        resource_model = apps.get_model("core", resource)
        default_org_resources = resource_model.objects.filter(
            organization=default_org
        )
        default_org_resources.objects.update(organization=None)


class Migration(migrations.Migration):
    dependencies = [
        (
            "core",
            "0032_organization_team_and_more",
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
