import os

from django.conf import settings
from django.db import migrations

SA_NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def legacy_activation_namespace() -> str:
    """Return the namespace used by Kubernetes Jobs before this feature.

    The deprecated override is the only pre-feature setting that could place
    activation Jobs outside the control-plane namespace.  The new default
    namespace setting is intentionally ignored because it may be configured
    while this migration is running and applies only to new Jobs.
    """
    old_override = os.environ.get("EDA_ACTIVATION_JOB_NAMESPACE", "").strip()
    if old_override:
        return old_override

    try:
        with open(SA_NAMESPACE_FILE, encoding="utf-8") as namespace_file:
            namespace = namespace_file.read().strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Cannot backfill legacy activation Job namespaces because "
            f"{SA_NAMESPACE_FILE} does not exist."
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
    RulebookProcess.objects.using(db_alias).filter(
        activation_job_namespace__isnull=True
    ).update(activation_job_namespace=legacy_activation_namespace())


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0075_rulebookprocess_activation_job_namespace"),
    ]

    operations = [
        migrations.RunPython(
            backfill_rulebook_process_activation_job_namespace,
            migrations.RunPython.noop,
        ),
    ]
