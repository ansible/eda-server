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
from unittest import mock

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
def test_purge_log_records_default_retention_is_disabled(capsys):
    with override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=0):
        output = call_command("purge_log_records")
    assert output.startswith("No logs purged")
    assert "No logs purged" in capsys.readouterr().out


@pytest.mark.django_db
def test_purge_log_records_with_nonexist_activation(capsys):
    # With global purging, even non-existent activation filters will
    # still purge old logs globally (if any exist)
    args = ("--activation-ids", "42", "--date", "2024-10-01")
    call_command("purge_log_records", *args)
    captured = capsys.readouterr()

    # Should report either no old logs found, or global purge count
    assert (
        "No log records found older than 2024-10-01" in captured.out
        or "Purged" in captured.out
    )

    args = ("--activation-names", "na", "--date", "2024-10-01")
    call_command("purge_log_records", *args)
    captured = capsys.readouterr()

    assert (
        "No log records found older than 2024-10-01" in captured.out
        or "Purged" in captured.out
    )


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
            activations[0].id,
            activations[1].id,
            "--date",
            date_str,
            "--audit-trail",
        )
    elif identifiers == "names":
        args = (
            "--activation-names",
            activations[0].name,
            activations[1].name,
            "--date",
            date_str,
            "--audit-trail",
        )
    else:
        args = (
            "--date",
            date_str,
            "--audit-trail",
        )

    call_command(command, *args)

    captured = capsys.readouterr()

    if cutoff_days < 10:
        # Global purge: all original logs deleted, audit logs created for
        # all 4 RulebookProcess instances
        assert models.RulebookProcessLog.objects.count() == 4

        for log_record in models.RulebookProcessLog.objects.all():
            assert f"All log records older than {date_str}" in log_record.log
    else:
        # Global purge: only 30-day logs deleted, 10-day logs remain,
        # audit logs created for all 4 RulebookProcess instances
        assert models.RulebookProcessLog.objects.count() == 8

        # Check audit logs exist for all instances
        audit_logs = models.RulebookProcessLog.objects.filter(
            log__contains=f"All log records older than {date_str}"
        )
        assert audit_logs.count() == 4

        # Check that 10-day logs still exist (not purged)
        original_logs = models.RulebookProcessLog.objects.exclude(
            log__contains="purged"
        )
        assert original_logs.count() == 4

    assert "Purged" in captured.out
    assert "globally" in captured.out


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
def test_purge_without_activation_filter_handles_null_correctly(
    null_activation_test_data, capsys
):
    """Test purge without activation filter includes NULL records.
    This tests the customer scenario."""

    # Get initial counts
    initial_log_count = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).count()
    assert initial_log_count == 4, "Should have 4 test log records"

    # Test purge without activation filtering (customer's command scenario)
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    call_command(
        "purge_log_records",
        "--date",
        cutoff_date,
        "--audit-trail",
        verbosity=3,
    )

    captured = capsys.readouterr()

    # Check that logs were purged
    remaining_test_logs = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).exclude(log__contains="purged")

    # Both NULL and normal activation logs should be purged in this scenario
    assert (
        remaining_test_logs.count() == 0
    ), "All test logs should be purged when no activation filter is used"
    assert "Purged" in captured.out
    assert "globally" in captured.out


@pytest.mark.django_db
def test_purge_with_activation_filter_now_includes_null_fix(
    null_activation_test_data, capsys
):
    """Purge includes NULL records with filters."""

    # Get initial counts
    initial_log_count = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).count()
    assert initial_log_count == 4, "Should have 4 test log records"

    # Test purge WITH activation filtering - this should now include
    # NULL records
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    activation_id = null_activation_test_data["activation"].id

    call_command(
        "purge_log_records",
        "--activation-ids",
        str(activation_id),
        "--date",
        cutoff_date,
        "--audit-trail",
        verbosity=3,
    )

    captured = capsys.readouterr()

    # Check what logs remain
    remaining_test_logs = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).exclude(log__contains="purged")

    # Verify the fix: NULL activation logs should now be purged
    null_activation_logs = [
        log
        for log in remaining_test_logs
        if log.activation_instance.activation_id is None
    ]

    # This validates the fix: NULL activation logs should now be
    # included in purge
    assert len(null_activation_logs) == 0, (
        "All NULL activation logs should be purged "
        "when using --activation-ids filter"
    )

    # Also verify that normal activation logs WERE purged
    normal_activation_logs = [
        log
        for log in remaining_test_logs
        if log.activation_instance.activation_id is not None
    ]
    assert (
        len(normal_activation_logs) == 0
    ), "Normal activation logs should have been purged"

    assert "Created 2 audit trail entries." in captured.out


@pytest.mark.django_db
def test_purge_with_activation_name_filter_also_includes_null_fix(
    null_activation_test_data, capsys
):
    """Test that the fix also works when using --activation-names parameter."""

    # Get initial counts
    initial_log_count = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).count()
    assert initial_log_count == 4, "Should have 4 test log records"

    # Test purge with activation NAME filtering - should now include
    # NULL records (fix)
    cutoff_date = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    activation_name = null_activation_test_data["activation"].name

    call_command(
        "purge_log_records",
        "--activation-names",
        activation_name,
        "--date",
        cutoff_date,
        "--audit-trail",
        verbosity=3,
    )

    captured = capsys.readouterr()

    # Check what logs remain
    remaining_test_logs = models.RulebookProcessLog.objects.filter(
        log__contains="for null test"
    ).exclude(log__contains="purged")

    # Verify the fix: NULL activation logs should now be purged
    # with name filtering too
    null_activation_logs = [
        log
        for log in remaining_test_logs
        if log.activation_instance.activation_id is None
    ]

    # This validates the fix works with activation name filtering
    assert len(null_activation_logs) == 0, (
        "All NULL activation logs should be purged "
        "when using --activation-names filter"
    )

    assert "Created 2 audit trail entries." in captured.out


@pytest.mark.django_db
def test_purge_without_audit_trail_does_not_create_audit_logs(
    prepare_log_records, capsys
):
    cutoff = (timezone.now() - timedelta(days=15)).strftime("%Y-%m-%d")
    output = call_command("purge_log_records", "--date", cutoff)

    assert output.startswith("Purged 4 log records")
    assert models.RulebookProcessLog.objects.count() == 4
    assert not models.RulebookProcessLog.objects.filter(
        log__contains="were purged at"
    ).exists()
    assert "Purged 4 log records" in capsys.readouterr().out


@pytest.mark.django_db
def test_purge_retention_setting_deletes_globally(prepare_log_records):
    with override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=15):
        output = call_command("purge_log_records")

    assert output.startswith("Purged 4 log records")
    assert models.RulebookProcessLog.objects.count() == 4


@pytest.mark.django_db
@pytest.mark.parametrize(
    "args",
    [
        ("--date", "2026-01-01", "--retention-duration", "P1D"),
        ("--retention-duration", "P0D"),
        ("--retention-duration", "-P1D"),
        ("--retention-duration", "not-a-duration"),
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
def test_activation_filter_selects_audit_targets_only(
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
        "--audit-trail",
    )

    audit_logs = models.RulebookProcessLog.objects.filter(
        log__contains="were purged at"
    )
    assert output.startswith("Purged 8 log records")
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
        log_timestamp > cutoff_timestamp
        for log_timestamp in audit_logs.values_list("log_timestamp", flat=True)
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
    monkeypatch.setattr(delete_log_util, "DELETE_BATCH_SIZE", 2)
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

    assert (
        delete_log_util.delete_logs_older_than(
            datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc)
        )
        == 5
    )
    assert not models.RulebookProcessLog.objects.filter(
        pk__in=[log.pk for log in logs]
    ).exists()


@pytest.mark.django_db
def test_retention_stops_at_initial_highest_qualifying_id(
    default_activation_instance, monkeypatch
):
    monkeypatch.setattr(delete_log_util, "DELETE_BATCH_SIZE", 1)
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
        datetime(1970, 1, 1, 0, 0, 2, tzinfo=datetime_timezone.utc)
    )

    assert deleted == 2
    assert models.RulebookProcessLog.objects.filter(pk=new_log[0].pk).exists()


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


@pytest.mark.django_db
def test_retention_failure_reports_committed_batch_count(
    default_activation_instance, monkeypatch
):
    monkeypatch.setattr(delete_log_util, "DELETE_BATCH_SIZE", 1)
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
        delete_log_util.delete_logs_older_than(cutoff)

    assert error.value.deleted_count == 1
    assert models.RulebookProcessLog.objects.count() == 2


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
