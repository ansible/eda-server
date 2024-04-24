import logging

from django.db import migrations, models

logger = logging.getLogger(
    "aap_eda.core.migrations.0036_alter_activation_extra_var_and_more"
)


def migrate_extra_var_data(apps, schema_editor):
    Activation = apps.get_model("core", "Activation")  # noqa N806
    ExtraVar = apps.get_model("core", "ExtraVar")  # noqa N806
    for activation in Activation.objects.all():
        if activation.extra_var:
            logger.info(
                f"Migrating ExtraVar data with ID={activation.extra_var}"
            )
            extra_var = ExtraVar.objects.filter(
                id=activation.extra_var
            ).first()
            activation.extra_var = extra_var.extra_var
            activation.save(update_fields=["extra_var"])


def create_extra_var_objects(apps, schema_editor):
    Activation = apps.get_model("core", "Activation")  # noqa N806
    ExtraVar = apps.get_model("core", "ExtraVar")  # noqa N806
    for activation in Activation.objects.all():
        if activation.extra_var:
            logger.info(
                f"Creating ExtraVar object for data: {activation.extra_var}"
            )
            extra_var = ExtraVar.objects.create(extra_var=activation.extra_var)
            activation.extra_var = extra_var.id
            activation.save(update_fields=["extra_var"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0035_remove_role_permissions_remove_user_roles_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activation",
            name="extra_var",
            field=models.TextField(null=True),
        ),
        migrations.RunPython(
            migrate_extra_var_data, reverse_code=create_extra_var_objects
        ),
        migrations.AlterField(
            model_name="eventstream",
            name="extra_var",
            field=models.TextField(null=True),
        ),
        migrations.DeleteModel(
            name="ExtraVar",
        ),
    ]
