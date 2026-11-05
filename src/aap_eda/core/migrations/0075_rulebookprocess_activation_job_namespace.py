from django.conf import settings
from django.db import migrations, models

SA_NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def legacy_activation_namespace() -> str:
    """Return the namespace used by Kubernetes Jobs before this feature.

    Before this feature, Kubernetes activation Jobs ran in the EDA
    control-plane namespace. The configured default namespace is intentionally
    ignored because it applies only to new Jobs.
    """
    try:
        with open(SA_NAMESPACE_FILE, encoding="utf-8") as namespace_file:
            namespace = namespace_file.read().strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Cannot backfill legacy activation Job namespaces because "
            f"{SA_NAMESPACE_FILE} does not exist."
        ) from exc
    except PermissionError as exc:
        raise RuntimeError(
            "Cannot backfill legacy activation Job namespaces because "
            f"{SA_NAMESPACE_FILE} is not readable."
        ) from exc

    if not namespace:
        raise RuntimeError(
            "Cannot backfill legacy activation Job namespaces because "
            f"{SA_NAMESPACE_FILE} is empty."
        )

    return namespace


def backfill_rulebook_process_activation_job_namespace(apps, schema_editor):
    """Record the legacy Kubernetes namespace for existing processes."""
    if settings.DEPLOYMENT_TYPE != "k8s":
        return

    RulebookProcess = apps.get_model("core", "RulebookProcess")  # noqa: N806
    db_alias = schema_editor.connection.alias
    processes = RulebookProcess.objects.using(db_alias).filter(
        activation_job_namespace__isnull=True
    )
    if not processes.exists():
        return

    processes.update(activation_job_namespace=legacy_activation_namespace())


class AddFieldIfAbsent(migrations.AddField):
    """Add/validate the column forward and retain it on database rollback."""

    def database_forwards(
        self, app_label, schema_editor, from_state, to_state
    ):
        """Add the field if absent, or validate the existing column."""
        connection = schema_editor.connection
        model = to_state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(connection.alias, model):
            return

        field = model._meta.get_field(self.name)
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(
                cursor, model._meta.db_table
            )

        existing_column = next(
            (column for column in columns if column.name == field.column), None
        )
        if existing_column is None:
            return super().database_forwards(
                app_label, schema_editor, from_state, to_state
            )

        existing_type = connection.introspection.get_field_type(
            existing_column.type_code, existing_column
        )
        expected_type = field.get_internal_type()
        if (
            existing_type != expected_type
            or existing_column.null_ok != field.null
        ):
            raise RuntimeError(
                f"Existing column {model._meta.db_table}.{field.column} is "
                f"incompatible: expected {expected_type} "
                f"(nullable={field.null}), found {existing_type} "
                f"(nullable={existing_column.null_ok})."
            )

    def database_backwards(
        self, app_label, schema_editor, from_state, to_state
    ):
        """Retain the database column while reverting migration state."""
        # The column may have existed before this migration on a supported
        # release database. Its ownership isn't persisted, so dropping it here
        # could break a downgrade. A leftover nullable column is harmless.
        return


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0074_awxtoken_ck_awx_token_name_not_empty_and_more"),
    ]

    operations = [
        AddFieldIfAbsent(
            model_name="rulebookprocess",
            name="activation_job_namespace",
            field=models.TextField(null=True),
        ),
        migrations.RunPython(
            backfill_rulebook_process_activation_job_namespace,
            migrations.RunPython.noop,
        ),
    ]
