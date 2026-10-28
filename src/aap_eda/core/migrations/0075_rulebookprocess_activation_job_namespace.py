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


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0074_awxtoken_ck_awx_token_name_not_empty_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookprocess",
            name="activation_job_namespace",
            field=models.TextField(null=True),
        ),
        migrations.RunPython(
            backfill_rulebook_process_activation_job_namespace,
            migrations.RunPython.noop,
        ),
    ]
