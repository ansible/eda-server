#  Copyright 2024 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from datetime import datetime, timedelta, timezone as datetime_timezone
from math import ceil
from unittest import mock
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.db.models.query import QuerySet
from django.test import override_settings
from django.utils import timezone

from aap_eda.core import enums, models
from aap_eda.core.utils import delete_log_util
from aap_eda.core.utils.log_retention import retention_cutoff


def _audit_markers():
    return models.RulebookProcessLog.objects.filter(log__startswith="Purged ")


@pytest.fixture
def prepare_log_records(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
) -> list[models.Activation]:
    activation_30_days_ago = models.Activation.objects.create(
        name="activation-30-days-ago",
        description="Activation 30 days ago",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )

    instances_30_days_ago = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="activation-30-days-ago-instance-1",
                activation=activation_30_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.STOPPED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.STOPPED
                ],
                organization=default_organization,
            ),
            models.RulebookProcess(
                name="activation-30-days-ago-instance-2",
                activation=activation_30_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.FAILED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.FAILED
                ],
                organization=default_organization,
            ),
        ]
    )

    activation_10_days_ago = models.Activation.objects.create(
        name="activation-10-days-ago",
        description="Activation 10 days ago",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )

    instances_10_days_ago = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="activation-10-days-ago-instance-1",
                activation=activation_10_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.COMPLETED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.COMPLETED
                ],
                organization=default_organization,
            ),
            models.RulebookProcess(
                name="activation-10-days-ago-instance-2",
                activation=activation_10_days_ago,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.RUNNING,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.RUNNING
                ],
                organization=default_organization,
            ),
        ]
    )

    log_timestamp_10_days_ago = timezone.now() - timedelta(days=10)
    log_timestamp_30_days_ago = timezone.now() - timedelta(days=30)

    models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-1",
                activation_instance=instances_30_days_ago[0],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-2",
                activation_instance=instances_30_days_ago[0],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-3",
                activation_instance=instances_30_days_ago[1],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-30-days-ago-log-4",
                activation_instance=instances_30_days_ago[1],
                log_timestamp=int(log_timestamp_30_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-1",
                activation_instance=instances_10_days_ago[0],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-2",
                activation_instance=instances_10_days_ago[0],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-3",
                activation_instance=instances_10_days_ago[1],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
            models.RulebookProcessLog(
                log="activation-instance-10-days-ago-log-4",
                activation_instance=instances_10_days_ago[1],
                log_timestamp=int(log_timestamp_10_days_ago.timestamp()),
            ),
        ]
    )

    return [activation_30_days_ago, activation_10_days_ago]


@pytest.mark.django_db
def test_purge_log_records_requires_explicit_cutoff_even_with_setting():
    with override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=0):
        with pytest.raises(CommandError, match="Exactly one"):
            call_command("purge_log_records")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "selector, expected",
    [
        (("--activation-ids", "999999999"), "Unknown activation IDs"),
        (("--activation-names", "missing-name"), "Unknown activation names"),
    ],
)
def test_unknown_selector_rejects_before_deleting(
    prepare_log_records, selector, expected
):
    original_ids = set(
        models.RulebookProcessLog.objects.values_list("id", flat=True)
    )

    with pytest.raises(CommandError, match=expected):
        call_command("purge_log_records", *selector, "--date", "2024-10-01")

    assert set(
        models.RulebookProcessLog.objects.values_list("id", flat=True)
    ) == (original_ids)


@pytest.mark.parametrize(
    "identifiers, cutoff_days",
    [("ids", 15), ("names", 5), ("none", 15), ("none", 5)],
)
@pytest.mark.django_db
def test_purge_log_records(
    prepare_log_records, capsys, identifiers, cutoff_days
):
    activations = prepare_log_records

    assert models.RulebookProcessLog.objects.count() == 8

    command = "purge_log_records"

    ts = timezone.now() - timedelta(days=cutoff_days)
    date_str = ts.strftime("%Y-%m-%d")

    if identifiers == "ids":
        args = (
            "--activation-ids",
            str(activations[0].id),
            str(activations[1].id),
            "--date",
            date_str,
        )
    elif identifiers == "names":
        args = (
            "--activation-names",
            activations[0].name,
            activations[1].name,
            "--date",
            date_str,
        )
    else:
        args = (
            "--date",
            date_str,
        )

    call_command(command, *args)

    captured = capsys.readouterr()

    if cutoff_days < 10:
        # All four processes lose rows and receive their own marker.
        assert models.RulebookProcessLog.objects.count() == 4

        for log_record in models.RulebookProcessLog.objects.all():
            assert f"Purged 2 log records older than {date_str}" in (
                log_record.log
            )
            assert "[Recorded at:" in log_record.log
    else:
        # Only the two older processes lose rows and receive markers.
        assert models.RulebookProcessLog.objects.count() == 6

        audit_logs = models.RulebookProcessLog.objects.filter(
            log__contains=f"Purged 2 log records older than {date_str}"
        )
        assert audit_logs.count() == 2
        assert all("[Recorded at:" in row.log for row in audit_logs)

        # Check that 10-day logs still exist (not purged)
        original_logs = models.RulebookProcessLog.objects.filter(
            log__startswith="activation-instance-10-days-ago"
        )
        assert original_logs.count() == 4

    assert "Purged" in captured.out
    assert (
        "globally" if identifiers == "none" else "for selected activations"
    ) in captured.out


@pytest.fixture
def null_activation_test_data(
    default_organization,
    default_user,
    default_project,
    default_decision_environment,
    default_rulebook,
):
    """Setup test data including a RulebookProcess with NULL activation."""

    # Create a normal activation
    activation = models.Activation.objects.create(
        name="test-activation-null-bug",
        description="Test activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var={},
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )

    # Create RulebookProcess with normal activation
    normal_process = models.RulebookProcess.objects.create(
        name="normal-process-null-test",
        activation=activation,
        status=enums.ActivationStatus.STOPPED,
        organization=default_organization,
    )

    # Create RulebookProcess with NULL activation using raw SQL
    # This bypasses the model validation
    with transaction.atomic():
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO core_rulebook_process
            (name, status, git_hash, parent_type, started_at,
             organization_id, activation_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            [
                "null-activation-process-test",
                enums.ActivationStatus.STOPPED,
                "",
                enums.ProcessParentType.ACTIVATION,
                timezone.now(),
                default_organization.id,
                None,  # NULL activation
            ],
        )

    # Get the null process object
    null_process = models.RulebookProcess.objects.get(
        name="null-activation-process-test"
    )

    # Create timestamp for old logs (20 days ago)
    old_timestamp = timezone.now() - timedelta(days=20)

    # Create log records for both processes
    models.RulebookProcessLog.objects.bulk_create(
        [
            # Logs for normal process
            models.RulebookProcessLog(
                log="Normal process log for null test 1",
                activation_instance=normal_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
            models.RulebookProcessLog(
                log="Normal process log for null test 2",
                activation_instance=normal_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
            # Logs for NULL activation process
            models.RulebookProcessLog(
                log="NULL activation process log for null test 1",
                activation_instance=null_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
            models.RulebookProcessLog(
                log="NULL activation process log for null test 2",
                activation_instance=null_process,
                log_timestamp=int(old_timestamp.timestamp()),
            ),
        ]
    )

    return {
        "activation": activation,
        "normal_process": normal_process,
        "null_process": null_process,
    }


@pytest.mark.django_db
def test_global_purge_includes_orphan_and_marks_each_process(
    null_activation_test_data,
):
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    output = call_command("purge_log_records", "--date", cutoff_date)

    assert output.startswith("Purged 4 log records")
    assert "globally" in output
    assert not models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).exists()
    markers = _audit_markers()
    assert markers.count() == 2
    orphan_marker = markers.get(
        activation_instance=null_activation_test_data["null_process"]
    )
    assert "Purged 2 log records older than" in orphan_marker.log
    assert "Activation Lifecycle ID: unavailable (orphaned process)" in (
        orphan_marker.log
    )


@pytest.mark.django_db
@pytest.mark.parametrize("selector", ["id", "name"])
def test_scoped_purge_preserves_orphan(null_activation_test_data, selector):
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    activation = null_activation_test_data["activation"]
    option, value = (
        ("--activation-ids", str(activation.id))
        if selector == "id"
        else ("--activation-names", activation.name)
    )

    output = call_command(
        "purge_log_records", option, value, "--date", cutoff_date
    )

    assert output.startswith("Purged 2 log records")
    assert "for selected activations" in output
    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance=null_activation_test_data["null_process"],
            log__contains="for null test",
        ).count()
        == 2
    )
    assert not models.RulebookProcessLog.objects.filter(
        activation_instance=null_activation_test_data["normal_process"],
        log__contains="for null test",
    ).exists()


@pytest.mark.django_db
def test_purge_without_audit_trail_does_not_create_audit_logs(
    prepare_log_records, capsys
):
    cutoff = (timezone.now() - timedelta(days=15)).strftime("%Y-%m-%d")
    output = call_command(
        "purge_log_records", "--date", cutoff, "--audit-trail=false"
    )

    assert output.startswith("Purged 4 log records")
    assert models.RulebookProcessLog.objects.count() == 4
    assert not _audit_markers().exists()
    assert "Purged 4 log records" in capsys.readouterr().out


@pytest.mark.django_db
def test_purge_retention_setting_does_not_supply_cutoff(prepare_log_records):
    with override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=15):
        with pytest.raises(CommandError, match="Exactly one"):
            call_command("purge_log_records")

    assert models.RulebookProcessLog.objects.count() == 8


@pytest.mark.django_db
@pytest.mark.parametrize("batch_size", [0, -1, 50_001, True, "2", 1.5, None])
def test_programmatic_batch_size_rejected_before_deletion(
    default_activation_instance, batch_size
):
    log = models.RulebookProcessLog.objects.create(
        activation_instance=default_activation_instance,
        log="must remain",
        log_timestamp=1,
    )

    with pytest.raises(CommandError, match="log_delete_batch_size"):
        call_command(
            "purge_log_records",
            date="2024-01-01",
            log_delete_batch_size=batch_size,
        )

    assert models.RulebookProcessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("batch_size", [0, -1, 50_001, True, "2", 1.5, None])
def test_utility_rejects_invalid_batch_size_before_deletion(
    default_activation_instance, batch_size
):
    log = models.RulebookProcessLog.objects.create(
        activation_instance=default_activation_instance,
        log="must remain",
        log_timestamp=1,
    )

    cutoff = datetime(2024, 1, 1, tzinfo=datetime_timezone.utc)
    with pytest.raises(ValueError, match="log_delete_batch_size"):
        delete_log_util.delete_logs_older_than(
            cutoff,
            log_delete_batch_size=batch_size,
        )

    assert models.RulebookProcessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("batch_size", ["0", "50001", "not-an-integer"])
def test_cli_rejects_invalid_batch_size_before_deletion(
    default_activation_instance, batch_size
):
    log = models.RulebookProcessLog.objects.create(
        activation_instance=default_activation_instance,
        log="must remain",
        log_timestamp=1,
    )

    with pytest.raises(CommandError):
        call_command(
            "purge_log_records",
            "--date",
            "2024-01-01",
            "--log-delete-batch-size",
            batch_size,
        )

    assert models.RulebookProcessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_cli_batch_size_defaults_to_10000_and_accepts_50000():
    with mock.patch(
        "aap_eda.core.management.commands.purge_log_records."
        "delete_logs_older_than",
        return_value=0,
    ) as delete_logs:
        call_command("purge_log_records", "--date", "2024-01-01")
        assert delete_logs.call_args.kwargs["log_delete_batch_size"] == 10_000

        call_command(
            "purge_log_records",
            "--date",
            "2024-01-01",
            "--log-delete-batch-size",
            "50000",
        )
        assert delete_logs.call_args.kwargs["log_delete_batch_size"] == 50_000


def test_large_activation_scope_caps_effective_log_batch_size():
    with mock.patch.object(
        delete_log_util,
        "resolve_activation_ids",
        return_value=set(range(20_000)),
    ):
        options = delete_log_util._validate_purge_options(
            datetime(2024, 1, 1, tzinfo=datetime_timezone.utc),
            activation_ids=[1],
            activation_names=None,
            audit_trail=True,
            internal_job_uuid=None,
            purge_all_logs=False,
            log_delete_batch_size=50_000,
        )

    assert options.log_delete_batch_size == 45_531


@pytest.mark.django_db
@pytest.mark.parametrize(
    "args",
    [
        ("--date", "2026-01-01", "--retention-duration", "P1D"),
        ("--retention-duration", "P0D"),
        ("--retention-duration", "-P1D"),
        ("--retention-duration", "not-a-duration"),
        ("--date", "not-a-date"),
        ("--date", "2999-01-01"),
    ],
)
def test_purge_rejects_invalid_retention_arguments(args):
    with pytest.raises(CommandError):
        call_command("purge_log_records", *args)


@pytest.mark.parametrize(
    "now, duration, expected",
    [
        (
            datetime(2026, 3, 31, 12, tzinfo=datetime_timezone.utc),
            "P1M",
            datetime(2026, 2, 28, 12, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(2024, 3, 31, 12, tzinfo=datetime_timezone.utc),
            "P1M",
            datetime(2024, 2, 29, 12, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(2024, 2, 29, 12, tzinfo=datetime_timezone.utc),
            "P1Y",
            datetime(2023, 2, 28, 12, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(
                2026,
                10,
                1,
                0,
                30,
                tzinfo=timezone.get_fixed_timezone(120),
            ),
            "P1D",
            datetime(2026, 9, 29, 22, 30, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(2026, 10, 21, 12, tzinfo=datetime_timezone.utc),
            "PT30S",
            datetime(2026, 10, 21, 11, 59, 30, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(2026, 10, 21, 12, tzinfo=datetime_timezone.utc),
            "PT5M",
            datetime(2026, 10, 21, 11, 55, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(2026, 10, 21, 12, tzinfo=datetime_timezone.utc),
            "PT2H",
            datetime(2026, 10, 21, 10, tzinfo=datetime_timezone.utc),
        ),
        (
            datetime(2026, 10, 21, 12, tzinfo=datetime_timezone.utc),
            "P2W",
            datetime(2026, 10, 7, 12, tzinfo=datetime_timezone.utc),
        ),
    ],
)
def test_retention_cutoff_calendar_and_timezone_policy(
    now, duration, expected
):
    assert retention_cutoff(duration, now=now) == expected


@pytest.mark.parametrize("filter_by", ["ids", "names"])
@pytest.mark.django_db
def test_activation_filter_limits_deletion_and_markers(
    prepare_log_records, filter_by
):
    selected_activation = prepare_log_records[0]
    cutoff = (timezone.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    option = "--activation-ids" if filter_by == "ids" else "--activation-names"
    value = (
        str(selected_activation.id)
        if filter_by == "ids"
        else selected_activation.name
    )

    output = call_command(
        "purge_log_records",
        option,
        value,
        "--date",
        cutoff,
    )

    audit_logs = _audit_markers()
    assert output.startswith("Purged 4 log records")
    assert audit_logs.count() == 2
    assert set(
        audit_logs.values_list("activation_instance__activation_id", flat=True)
    ) == {selected_activation.id}
    cutoff_timestamp = (
        datetime.strptime(cutoff, "%Y-%m-%d")
        .replace(tzinfo=datetime_timezone.utc)
        .timestamp()
    )
    assert all(
        log_timestamp >= cutoff_timestamp
        for log_timestamp in audit_logs.values_list("log_timestamp", flat=True)
    )
    assert (
        models.RulebookProcessLog.objects.filter(
            activation_instance__activation_id=prepare_log_records[1].id,
            log__startswith="activation-instance-",
        ).count()
        == 4
    )


@pytest.mark.django_db
def test_retention_duration_deletes_strictly_older_rows_across_activations(
    default_activation_instances,
):
    cutoff = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
    older, equal, newer = [
        models.RulebookProcessLog.objects.create(
            log=f"boundary-{timestamp}",
            activation_instance=default_activation_instances[index % 2],
            log_timestamp=timestamp,
        )
        for index, timestamp in enumerate(
            (
                cutoff.timestamp() - 1,
                cutoff.timestamp(),
                cutoff.timestamp() + 1,
            )
        )
    ]

    deleted = delete_log_util.delete_logs_older_than(cutoff)

    assert deleted == 1
    assert not models.RulebookProcessLog.objects.filter(pk=older.pk).exists()
    assert (
        models.RulebookProcessLog.objects.filter(
            pk__in=[equal.pk, newer.pk]
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_retention_batches_continue_after_more_than_one_batch(
    default_activation_instance, monkeypatch
):
    logs = models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log=f"batch-{index}",
                activation_instance=default_activation_instance,
                log_timestamp=1,
            )
            for index in range(5)
        ]
    )
    original_delete = QuerySet.delete
    deleted_batch_sizes = []

    def record_batch_size(queryset):
        deleted_batch_sizes.append(queryset.count())
        return original_delete(queryset)

    monkeypatch.setattr(QuerySet, "delete", record_batch_size)

    assert (
        delete_log_util.delete_logs_older_than(
            datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc),
            log_delete_batch_size=2,
        )
        == 5
    )
    assert not models.RulebookProcessLog.objects.filter(
        pk__in=[log.pk for log in logs]
    ).exists()
    assert deleted_batch_sizes == [2, 2, 1]
    marker = _audit_markers().get()
    assert "Purged 5 log records older than" in marker.log
    assert marker.log_created_at is not None
    assert (
        f"Recorded at: {delete_log_util._utc_text(marker.log_created_at)}"
        in marker.log
    )


@pytest.mark.django_db
def test_retention_stops_at_initial_highest_qualifying_id(
    default_activation_instance, monkeypatch
):
    models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log=f"snapshot-{index}",
                activation_instance=default_activation_instance,
                log_timestamp=1,
            )
            for index in range(2)
        ]
    )
    original_delete = QuerySet.delete
    new_log = []
    calls = 0

    def insert_after_first_batch(queryset):
        nonlocal calls
        result = original_delete(queryset)
        calls += 1
        if calls == 1:
            new_log.append(
                models.RulebookProcessLog.objects.create(
                    log="arrived-during-purge",
                    activation_instance=default_activation_instance,
                    log_timestamp=1,
                )
            )
        return result

    monkeypatch.setattr(QuerySet, "delete", insert_after_first_batch)
    deleted = delete_log_util.delete_logs_older_than(
        datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc),
        log_delete_batch_size=1,
    )

    assert deleted == 2
    assert models.RulebookProcessLog.objects.filter(pk=new_log[0].pk).exists()


@pytest.mark.django_db
def test_batch_delete_rechecks_cutoff_after_candidate_selection(
    default_activation_instance, monkeypatch
):
    log = models.RulebookProcessLog.objects.create(
        log="changed-between-selection-and-delete",
        activation_instance=default_activation_instance,
        log_timestamp=1,
    )
    original_delete = QuerySet.delete

    def move_log_past_cutoff_before_delete(queryset):
        models.RulebookProcessLog.objects.filter(pk=log.pk).update(
            log_timestamp=3
        )
        return original_delete(queryset)

    monkeypatch.setattr(QuerySet, "delete", move_log_past_cutoff_before_delete)
    cutoff = datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc)

    assert delete_log_util.delete_logs_older_than(cutoff) == 0
    log.refresh_from_db()
    assert log.log_timestamp == 3
    assert models.RulebookProcessLog.objects.count() == 1


@pytest.mark.django_db
def test_retention_with_no_matching_rows_returns_zero(
    default_activation_instance,
):
    models.RulebookProcessLog.objects.create(
        log="new",
        activation_instance=default_activation_instance,
        log_timestamp=2,
    )
    assert (
        delete_log_util.delete_logs_older_than(
            datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc)
        )
        == 0
    )


@pytest.mark.django_db(transaction=True)
def test_retention_failure_reports_committed_batch_count(
    default_activation_instance, monkeypatch
):
    models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log=f"partial-{index}",
                activation_instance=default_activation_instance,
                log_timestamp=1,
            )
            for index in range(3)
        ]
    )
    original_delete = QuerySet.delete
    calls = 0

    def fail_second_delete(queryset):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected batch failure")
        return original_delete(queryset)

    monkeypatch.setattr(QuerySet, "delete", fail_second_delete)
    cutoff = datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc)
    with pytest.raises(delete_log_util.LogPurgeError) as error:
        delete_log_util.delete_logs_older_than(cutoff, log_delete_batch_size=1)

    assert error.value.deleted_count == 1
    assert models.RulebookProcessLog.objects.count() == 3
    marker = _audit_markers().get()
    assert "Purged 1 log record older than" in marker.log
    assert (
        models.RulebookProcessLog.objects.filter(
            log__startswith="partial-"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_retention_duration_cli_uses_execution_time_cutoff(
    default_activation_instance,
):
    cutoff_epoch = datetime(
        2026, 10, 20, tzinfo=datetime_timezone.utc
    ).timestamp()
    logs = models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log=f"duration-{index}",
                activation_instance=default_activation_instance,
                log_timestamp=timestamp,
            )
            for index, timestamp in enumerate(
                (cutoff_epoch - 1, cutoff_epoch, cutoff_epoch + 1)
            )
        ]
    )

    with mock.patch(
        "aap_eda.core.utils.log_retention.datetime"
    ) as mocked_datetime:
        mocked_datetime.now.return_value = datetime(
            2026, 10, 21, tzinfo=datetime_timezone.utc
        )
        mocked_datetime.timezone = datetime_timezone
        output = call_command(
            "purge_log_records", "--retention-duration", "P1D"
        )

    assert output.startswith("Purged 1 log records")
    assert not models.RulebookProcessLog.objects.filter(pk=logs[0].pk).exists()
    assert (
        models.RulebookProcessLog.objects.filter(
            pk__in=[logs[1].pk, logs[2].pk]
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_mixed_selectors_form_union_and_validate_all_before_delete(
    prepare_log_records,
):
    first, second = prepare_log_records
    cutoff = (timezone.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    original_ids = set(
        models.RulebookProcessLog.objects.values_list("id", flat=True)
    )

    with pytest.raises(CommandError, match="Unknown activation names"):
        call_command(
            "purge_log_records",
            "--activation-ids",
            str(first.id),
            "--activation-names",
            second.name,
            "missing-name",
            "--date",
            cutoff,
        )
    assert set(
        models.RulebookProcessLog.objects.values_list("id", flat=True)
    ) == (original_ids)

    output = call_command(
        "purge_log_records",
        "--activation-ids",
        str(first.id),
        "--activation-names",
        second.name,
        "--date",
        cutoff,
        "--audit-trail=false",
    )
    assert output.startswith("Purged 8 log records")
    assert "for selected activations" in output
    assert not models.RulebookProcessLog.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "options, error",
    [
        ({"activation-ids": []}, "Activation IDs must"),
        ({"activation-ids": [0]}, "Activation IDs must"),
        ({"activation-names": [" "]}, "Activation names cannot"),
    ],
)
def test_invalid_programmatic_selectors_never_delete(
    prepare_log_records, options, error
):
    with pytest.raises(CommandError, match=error):
        call_command("purge_log_records", date="2024-10-01", **options)
    assert models.RulebookProcessLog.objects.count() == 8


@pytest.mark.django_db
@pytest.mark.parametrize(
    "args",
    [
        ("--audit-trail",),
        ("--no-audit-trail",),
        ("--audit-trail=maybe",),
    ],
)
def test_audit_cli_rejects_unsupported_forms(prepare_log_records, args):
    with pytest.raises(CommandError):
        call_command("purge_log_records", "--date", "2024-10-01", *args)
    assert models.RulebookProcessLog.objects.count() == 8


@pytest.mark.django_db
def test_zero_row_result_creates_no_marker(default_activation_instance):
    log = models.RulebookProcessLog.objects.create(
        log="newer-than-cutoff",
        activation_instance=default_activation_instance,
        log_timestamp=int(timezone.now().timestamp()),
    )
    output = call_command(
        "purge_log_records", "--date", "2024-01-01", "--audit-trail=true"
    )

    assert output.startswith("Purged 0 log records")
    assert "globally" in output
    assert models.RulebookProcessLog.objects.get(pk=log.pk).log == (
        "newer-than-cutoff"
    )
    assert models.RulebookProcessLog.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_id", ["", "bad id", "bad|id", "bad\nid", "école", "a" * 129]
)
def test_invalid_internal_job_id_rejected_before_deletion(
    default_activation_instance, invalid_id
):
    log = models.RulebookProcessLog.objects.create(
        log="old",
        activation_instance=default_activation_instance,
        log_timestamp=1,
    )
    with pytest.raises(CommandError, match="must be a UUID or a custom ID"):
        call_command(
            "purge_log_records",
            date="2024-01-01",
            **{"internal-job-uuid": invalid_id},
        )
    assert models.RulebookProcessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_cli_valid_internal_uuid_is_in_default_audit_marker(
    default_activation_instance,
):
    models.RulebookProcessLog.objects.create(
        log="old",
        activation_instance=default_activation_instance,
        log_timestamp=1,
    )
    job_id = uuid4()

    output = call_command(
        "purge_log_records",
        "--date",
        "2024-01-01",
        "--audit-trail=true",
        "--internal-job-uuid",
        str(job_id).upper(),
    )

    assert output.startswith("Purged 1 log records")
    marker = _audit_markers().get()
    assert f"Purge Job ID: {job_id}" in marker.log
    assert "Purged 1 log record older than" in marker.log
    assert "[Recorded at:" in marker.log


@pytest.mark.django_db
def test_cli_custom_internal_job_id_is_in_audit_marker(
    default_activation_instance,
):
    models.RulebookProcessLog.objects.create(
        log="old",
        activation_instance=default_activation_instance,
        log_timestamp=1,
    )

    output = call_command(
        "purge_log_records",
        "--date",
        "2024-01-01",
        "--internal-job-uuid",
        "Freds-Troubleshootin-Logs",
    )

    assert output.startswith("Purged 1 log records")
    marker = _audit_markers().get()
    assert "Purge Job ID: Freds-Troubleshootin-Logs" in marker.log


@pytest.mark.django_db
def test_prior_markers_are_deleted_when_older_than_cutoff(
    default_activation_instance,
):
    process = default_activation_instance
    prior_recorded_at = datetime(2024, 2, 1, tzinfo=datetime_timezone.utc)
    old_marker = models.RulebookProcessLog.objects.create(
        activation_instance=process,
        log=(
            "Purged 1 log record older than 2024-01-01 00:00:00 UTC. "
            "[Recorded at: 2024-02-01 00:00:00 UTC]"
        ),
        log_timestamp=int(prior_recorded_at.timestamp()),
        log_created_at=prior_recorded_at,
    )
    ordinary = models.RulebookProcessLog.objects.create(
        activation_instance=process, log="ordinary", log_timestamp=1
    )
    cutoff = datetime(2024, 3, 1, tzinfo=datetime_timezone.utc)

    assert delete_log_util.delete_logs_older_than(cutoff) == 2
    first_marker = _audit_markers().get()
    assert not models.RulebookProcessLog.objects.filter(
        pk=ordinary.pk
    ).exists()
    assert not models.RulebookProcessLog.objects.filter(
        pk=old_marker.pk
    ).exists()
    assert "Purged 2 log records older than" in first_marker.log

    models.RulebookProcessLog.objects.filter(pk=first_marker.pk).update(
        log_timestamp=1
    )
    assert delete_log_util.delete_logs_older_than(cutoff) == 1
    assert not models.RulebookProcessLog.objects.filter(
        pk=first_marker.pk
    ).exists()
    replacement = _audit_markers().get()
    assert "Purged 1 log record older than" in replacement.log
    assert models.RulebookProcessLog.objects.count() == 1


@pytest.mark.django_db
def test_marker_uses_invocation_count_job_uuid_tracking_and_ceiled_timestamp(
    default_activation_instance,
):
    process = default_activation_instance
    activation = process.activation
    activation.log_tracking_id = " tracking-123 "
    activation.save(update_fields=["log_tracking_id"])
    models.RulebookProcessLog.objects.create(
        activation_instance=process, log="old", log_timestamp=1
    )
    job_id = uuid4()
    cutoff = datetime(
        2024, 1, 1, 0, 0, 0, 500000, tzinfo=datetime_timezone.utc
    )

    before_purge = timezone.now()
    assert (
        delete_log_util.delete_logs_older_than(
            cutoff, internal_job_uuid=str(job_id)
        )
        == 1
    )
    after_purge = timezone.now()
    marker = _audit_markers().get()
    assert (
        max(ceil(before_purge.timestamp()), ceil(cutoff.timestamp()))
        <= marker.log_timestamp
        <= max(ceil(after_purge.timestamp()), ceil(cutoff.timestamp()))
    )
    assert before_purge <= marker.log_created_at <= after_purge
    assert marker.log.startswith(
        "Purged 1 log record older than "
        "2024-01-01 00:00:00.500000 UTC. [Recorded at: "
    )
    assert marker.log.endswith(
        f" | Purge Job ID: {job_id} | "
        "Activation Lifecycle ID: tracking-123]"
    )

    models.RulebookProcessLog.objects.create(
        activation_instance=process, log="another old row", log_timestamp=1
    )
    assert delete_log_util.delete_logs_older_than(cutoff) == 1
    markers = list(_audit_markers())
    assert len(markers) == 2
    assert all("Purged 1 log record older than" in row.log for row in markers)
    assert (
        "Purge Job ID:"
        not in next(row for row in markers if row.pk != marker.pk).log
    )


@pytest.mark.django_db
def test_purge_all_logs_replaces_old_rows_and_markers_per_process(
    null_activation_test_data,
):
    normal = null_activation_test_data["normal_process"]
    orphan = null_activation_test_data["null_process"]
    prior_recorded_at = datetime(2024, 2, 1, tzinfo=datetime_timezone.utc)
    models.RulebookProcessLog.objects.create(
        activation_instance=normal,
        log=(
            "Purged 1 log record older than 2024-01-01 00:00:00 UTC. "
            "[Recorded at: 2024-02-01 00:00:00 UTC]"
        ),
        log_timestamp=int(prior_recorded_at.timestamp()),
        log_created_at=prior_recorded_at,
    )
    models.RulebookProcessLog.objects.create(
        activation_instance=normal,
        log="future ordinary log",
        log_timestamp=int(timezone.now().timestamp()) + 10000,
    )
    models.RulebookProcessLog.objects.create(
        activation_instance=orphan,
        log=(
            "Purged 1 log record older than 2024-01-01 00:00:00 UTC. "
            "[Recorded at: 2024-02-01 00:00:00 UTC]"
        ),
        log_timestamp=int(prior_recorded_at.timestamp()),
        log_created_at=prior_recorded_at,
    )
    old_ids = set(
        models.RulebookProcessLog.objects.values_list("id", flat=True)
    )
    job_id = uuid4()

    output = call_command(
        "purge_log_records",
        "--purge-all-logs",
        "--internal-job-uuid",
        str(job_id),
        "--log-delete-batch-size",
        "2",
    )

    assert output.startswith("Purged 7 log records globally")
    assert not models.RulebookProcessLog.objects.filter(
        pk__in=old_ids
    ).exists()
    markers = models.RulebookProcessLog.objects.all()
    assert markers.count() == 2
    normal_marker = markers.get(activation_instance=normal)
    orphan_marker = markers.get(activation_instance=orphan)
    assert "Purged 4 log records globally. [Recorded at:" in normal_marker.log
    assert "Purged 3 log records globally. [Recorded at:" in orphan_marker.log
    assert f"Purge Job ID: {job_id}" in normal_marker.log
    assert "Activation Lifecycle ID: unavailable (orphaned process)" in (
        orphan_marker.log
    )
    assert all(
        marker.log_created_at is not None
        and f"Recorded at: {delete_log_util._utc_text(marker.log_created_at)}"
        in marker.log
        for marker in markers
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "conflicting_options",
    [
        ("--date", "2024-01-01"),
        ("--retention-duration", "P1D"),
        ("--activation-ids", "1"),
        ("--activation-names", "example"),
        ("--audit-trail=false",),
    ],
)
def test_purge_all_logs_rejects_other_modes_before_deletion(
    default_activation_instance, conflicting_options
):
    log = models.RulebookProcessLog.objects.create(
        activation_instance=default_activation_instance,
        log="must remain",
        log_timestamp=1,
    )

    with pytest.raises(CommandError, match="purge-all-logs"):
        call_command(
            "purge_log_records", "--purge-all-logs", *conflicting_options
        )

    assert models.RulebookProcessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_purge_all_logs_rejects_programmatic_non_boolean_flag(
    default_activation_instance,
):
    log = models.RulebookProcessLog.objects.create(
        activation_instance=default_activation_instance,
        log="must remain",
        log_timestamp=1,
    )

    with pytest.raises(CommandError, match="must be a boolean flag"):
        call_command("purge_log_records", **{"purge-all-logs": "false"})

    assert models.RulebookProcessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_purge_all_logs_with_no_rows_creates_no_marker(
    default_activation_instance,
):
    output = call_command("purge_log_records", "--purge-all-logs")

    assert output.startswith("Purged 0 log records globally")
    assert "No audit markers created." in output
    assert not models.RulebookProcessLog.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_purge_all_logs_failure_keeps_committed_marker_count(
    default_activation_instance, monkeypatch
):
    models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                activation_instance=default_activation_instance,
                log=f"old-{index}",
                log_timestamp=1,
            )
            for index in range(2)
        ]
    )
    original_delete = QuerySet.delete
    calls = 0

    def fail_second_delete(queryset):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected batch failure")
        return original_delete(queryset)

    monkeypatch.setattr(QuerySet, "delete", fail_second_delete)
    with pytest.raises(CommandError, match="failed after 1 committed rows"):
        call_command(
            "purge_log_records",
            "--purge-all-logs",
            "--log-delete-batch-size",
            "1",
        )

    assert (
        models.RulebookProcessLog.objects.filter(
            log__startswith="old-"
        ).count()
        == 1
    )
    marker = _audit_markers().get()
    assert "Purged 1 log record globally." in marker.log
