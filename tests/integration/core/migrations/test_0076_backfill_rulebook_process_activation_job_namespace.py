from importlib import import_module
from unittest import mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from aap_eda.core import models


def get_historical_model(app_label, model_name, migration):
    """Get a model as it existed at a specific migration."""
    executor = MigrationExecutor(connection)
    state = executor.loader.project_state((app_label, migration))
    return state.apps.get_model(app_label, model_name)


@pytest.fixture
def rollback_migration():
    """Rollback to before the namespace field exists and restore later."""
    call_command("migrate", "core", "0074")
    yield
    call_command("migrate")


@pytest.mark.django_db(transaction=True)
def test_migration_records_control_plane_namespace(
    rollback_migration, default_organization, tmp_path
):
    """Pre-feature Kubernetes processes retain their original namespace."""
    HistoricalRulebookProcess = get_historical_model(  # noqa: N806
        "core",
        "RulebookProcess",
        "0074_awxtoken_ck_awx_token_name_not_empty_and_more",
    )
    process = HistoricalRulebookProcess.objects.create(
        name="legacy-process",
        activation_pod_id="activation-job-1-1",
        organization_id=default_organization.id,
    )

    namespace_file = tmp_path / "namespace"
    namespace_file.write_text("eda-control-plane\n", encoding="utf-8")
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0076_backfill_rulebook_process_activation_job_namespace"
    )

    with (
        mock.patch.object(settings, "DEPLOYMENT_TYPE", "k8s"),
        mock.patch.object(
            migration_module, "SA_NAMESPACE_FILE", str(namespace_file)
        ),
    ):
        call_command("migrate", "core", "0076")

    migrated_process = models.RulebookProcess.objects.get(pk=process.pk)
    assert migrated_process.activation_job_namespace == "eda-control-plane"
