from importlib import import_module
from unittest import mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from aap_eda.core import models

MIGRATION_0075 = "0075_rulebookprocess_activation_job_namespace"


def get_historical_model(app_label, model_name, migration):
    """Get a model as it existed at a specific migration."""
    executor = MigrationExecutor(connection)
    state = executor.loader.project_state((app_label, migration))
    return state.apps.get_model(app_label, model_name)


def add_namespace_column(definition="text"):
    """Add the namespace column to emulate a release's existing schema."""
    definitions = {
        "text": "TEXT NULL",
        "varchar": "VARCHAR(255) NULL",
        "text_not_null": "TEXT NOT NULL",
    }
    table = connection.ops.quote_name("core_rulebook_process")
    column = connection.ops.quote_name("activation_job_namespace")
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} "
            f"{definitions[definition]}"
        )


def drop_namespace_column():
    """Remove a test-created column, if one remains."""
    if "core_rulebook_process" not in connection.introspection.table_names():
        return

    table = connection.ops.quote_name("core_rulebook_process")
    column = connection.ops.quote_name("activation_job_namespace")
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")


def namespace_column_definition():
    """Return PostgreSQL's declared type and nullability for the column."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT data_type, is_nullable
              FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = %s
               AND column_name = %s
            """,
            ["core_rulebook_process", "activation_job_namespace"],
        )
        return cursor.fetchone()


def assert_nullable_text_column():
    """Verify the field is stored as nullable PostgreSQL text."""
    assert namespace_column_definition() == ("text", "YES")


@pytest.fixture
def rollback_migration():
    """Set up the pre-0075 schema and restore the current schema afterward."""
    assert connection.vendor == "postgresql"
    call_command("migrate", "core", "0074")
    drop_namespace_column()

    yield

    call_command("migrate", "core", "0074")
    drop_namespace_column()
    call_command("migrate")


@pytest.mark.django_db(transaction=True)
def test_migration_adds_nullable_text_field_when_column_is_absent(
    rollback_migration,
):
    """A fresh schema gets the field and records it in migration state."""
    assert namespace_column_definition() is None

    call_command("migrate", "core", "0075")

    assert_nullable_text_column()
    RulebookProcess = get_historical_model(  # noqa: N806
        "core", "RulebookProcess", MIGRATION_0075
    )
    field = RulebookProcess._meta.get_field("activation_job_namespace")
    assert field.get_internal_type() == "TextField"
    assert field.null


@pytest.mark.django_db(transaction=True)
def test_migration_backfills_namespace_for_existing_process(
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
        "0075_rulebookprocess_activation_job_namespace"
    )

    with (
        mock.patch.object(settings, "DEPLOYMENT_TYPE", "k8s"),
        mock.patch.object(
            migration_module, "SA_NAMESPACE_FILE", str(namespace_file)
        ),
    ):
        call_command("migrate", "core", "0075")

    migrated_process = models.RulebookProcess.objects.get(pk=process.pk)
    assert migrated_process.activation_job_namespace == "eda-control-plane"
    assert_nullable_text_column()


@pytest.mark.django_db(transaction=True)
def test_migration_skips_namespace_lookup_without_legacy_processes(
    rollback_migration,
):
    """An empty installation does not need the ServiceAccount namespace."""
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0075_rulebookprocess_activation_job_namespace"
    )

    with (
        mock.patch.object(settings, "DEPLOYMENT_TYPE", "k8s"),
        mock.patch.object(
            migration_module, "legacy_activation_namespace"
        ) as legacy_activation_namespace,
    ):
        call_command("migrate", "core", "0075")

    legacy_activation_namespace.assert_not_called()
    assert_nullable_text_column()


@pytest.mark.django_db(transaction=True)
def test_migration_reuses_existing_nullable_text_column_and_backfills(
    rollback_migration,
    default_organization,
    tmp_path,
):
    """Backfill null values while preserving existing namespace values."""
    HistoricalRulebookProcess = get_historical_model(  # noqa: N806
        "core",
        "RulebookProcess",
        "0074_awxtoken_ck_awx_token_name_not_empty_and_more",
    )
    process = HistoricalRulebookProcess.objects.create(
        name="legacy-release-process",
        activation_pod_id="activation-job-legacy-1",
        organization_id=default_organization.id,
    )
    process_with_namespace = HistoricalRulebookProcess.objects.create(
        name="legacy-release-process-with-namespace",
        activation_pod_id="activation-job-legacy-2",
        organization_id=default_organization.id,
    )
    add_namespace_column()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE core_rulebook_process "
            "SET activation_job_namespace = %s WHERE id = %s",
            ["existing-control-plane", process_with_namespace.pk],
        )
    recorder = MigrationRecorder(connection)
    assert not recorder.migration_qs.filter(
        app="core", name=MIGRATION_0075
    ).exists()

    namespace_file = tmp_path / "namespace"
    namespace_file.write_text("release-control-plane\n", encoding="utf-8")
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0075_rulebookprocess_activation_job_namespace"
    )
    with (
        mock.patch.object(settings, "DEPLOYMENT_TYPE", "k8s"),
        mock.patch.object(
            migration_module, "SA_NAMESPACE_FILE", str(namespace_file)
        ),
    ):
        call_command("migrate", "core", "0075")

    assert_nullable_text_column()
    migrated_process = models.RulebookProcess.objects.get(pk=process.pk)
    assert migrated_process.activation_job_namespace == "release-control-plane"
    migrated_process_with_namespace = models.RulebookProcess.objects.get(
        pk=process_with_namespace.pk
    )
    assert (
        migrated_process_with_namespace.activation_job_namespace
        == "existing-control-plane"
    )
    assert_nullable_text_column()


@pytest.mark.parametrize(
    ("definition", "expected_schema"),
    [
        ("varchar", ("character varying", "YES")),
        ("text_not_null", ("text", "NO")),
    ],
    ids=("wrong-type", "not-null"),
)
@pytest.mark.django_db(transaction=True)
def test_migration_rejects_incompatible_existing_column(
    rollback_migration, definition, expected_schema
):
    """An incompatible existing column fails with a clear diagnostic."""
    add_namespace_column(definition)

    with pytest.raises(
        RuntimeError,
        match=r"Existing column .* is incompatible: expected TextField",
    ):
        call_command("migrate", "core", "0075")

    assert namespace_column_definition() == expected_schema
    assert (
        not MigrationRecorder(connection)
        .migration_qs.filter(app="core", name=MIGRATION_0075)
        .exists()
    )


@pytest.mark.django_db(transaction=True)
def test_rollback_then_reapply_reuses_retained_column(
    rollback_migration, default_organization
):
    """Reapplying 0075 reuses its retained column after a rollback."""
    call_command("migrate", "core", "0075")
    RulebookProcess = get_historical_model(  # noqa: N806
        "core", "RulebookProcess", MIGRATION_0075
    )
    process = RulebookProcess.objects.create(
        name="retained-column-process",
        activation_pod_id="activation-job-retained-1",
        organization_id=default_organization.id,
        activation_job_namespace="retained-control-plane",
    )
    assert_nullable_text_column()

    call_command("migrate", "core", "0074")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT activation_job_namespace FROM core_rulebook_process "
            "WHERE id = %s",
            [process.pk],
        )
        assert cursor.fetchone()[0] == "retained-control-plane"
    assert_nullable_text_column()
    recorder = MigrationRecorder(connection)
    assert not recorder.migration_qs.filter(
        app="core", name=MIGRATION_0075
    ).exists()

    call_command("migrate", "core", "0075")

    RulebookProcess = get_historical_model(  # noqa: N806
        "core", "RulebookProcess", MIGRATION_0075
    )
    assert (
        RulebookProcess.objects.get(pk=process.pk).activation_job_namespace
        == "retained-control-plane"
    )
    assert_nullable_text_column()
    assert recorder.migration_qs.filter(
        app="core", name=MIGRATION_0075
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_rollback_then_reapply_reuses_preexisting_column(
    rollback_migration, default_organization
):
    """A retained compatible column is reused when migration state returns."""
    add_namespace_column()

    call_command("migrate", "core", "0075")
    RulebookProcess = get_historical_model(  # noqa: N806
        "core", "RulebookProcess", MIGRATION_0075
    )
    process = RulebookProcess.objects.create(
        name="preexisting-column-process",
        activation_pod_id="activation-job-preexisting-1",
        organization_id=default_organization.id,
        activation_job_namespace="preexisting-control-plane",
    )
    assert_nullable_text_column()

    call_command("migrate", "core", "0074")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT activation_job_namespace FROM core_rulebook_process "
            "WHERE id = %s",
            [process.pk],
        )
        assert cursor.fetchone()[0] == "preexisting-control-plane"
    assert_nullable_text_column()
    recorder = MigrationRecorder(connection)
    assert not recorder.migration_qs.filter(
        app="core", name=MIGRATION_0075
    ).exists()

    call_command("migrate", "core", "0075")

    RulebookProcess = get_historical_model(  # noqa: N806
        "core", "RulebookProcess", MIGRATION_0075
    )
    assert (
        RulebookProcess.objects.get(pk=process.pk).activation_job_namespace
        == "preexisting-control-plane"
    )
    assert_nullable_text_column()
    assert recorder.migration_qs.filter(
        app="core", name=MIGRATION_0075
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_migration_skips_column_when_router_disallows_model(
    rollback_migration,
):
    """Skip the database change when the router rejects the model."""
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0075_rulebookprocess_activation_job_namespace"
    )
    executor = MigrationExecutor(connection)
    from_state = executor.loader.project_state(
        ("core", "0074_awxtoken_ck_awx_token_name_not_empty_and_more")
    )
    to_state = executor.loader.project_state(("core", MIGRATION_0075))
    operation = migration_module.Migration.operations[0]

    with connection.schema_editor() as schema_editor:
        with mock.patch.object(
            operation, "allow_migrate_model", return_value=False
        ):
            operation.database_forwards(
                "core", schema_editor, from_state, to_state
            )

    assert namespace_column_definition() is None


def test_legacy_activation_namespace_missing_file_is_diagnostic(tmp_path):
    """Report a diagnostic when the Kubernetes namespace file is absent."""
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0075_rulebookprocess_activation_job_namespace"
    )

    with mock.patch.object(
        migration_module,
        "SA_NAMESPACE_FILE",
        str(tmp_path / "missing-namespace"),
    ):
        with pytest.raises(RuntimeError, match="does not exist"):
            migration_module.legacy_activation_namespace()


def test_legacy_activation_namespace_empty_file_is_diagnostic(tmp_path):
    """Report a diagnostic when the Kubernetes namespace file is empty."""
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0075_rulebookprocess_activation_job_namespace"
    )
    namespace_file = tmp_path / "namespace"
    namespace_file.write_text("", encoding="utf-8")

    with mock.patch.object(
        migration_module, "SA_NAMESPACE_FILE", str(namespace_file)
    ):
        with pytest.raises(RuntimeError, match="is empty"):
            migration_module.legacy_activation_namespace()


def test_migration_namespace_permission_error_is_diagnostic():
    """Report a clear diagnostic when the namespace file is unreadable."""
    migration_module = import_module(
        "aap_eda.core.migrations."
        "0075_rulebookprocess_activation_job_namespace"
    )

    with mock.patch("builtins.open", side_effect=PermissionError):
        with pytest.raises(RuntimeError, match="is not readable"):
            migration_module.legacy_activation_namespace()
