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

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from aap_eda.core import enums, models


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
def test_purge_log_records_missing_required_params():
    with pytest.raises(
        CommandError,
        match="Error: the following arguments are required: --date",
    ):
        call_command("purge_log_records")


@pytest.mark.django_db
def test_purge_log_records_with_nonexist_activation(capsys):
    args = ("--activation-ids", "42", "--date", "2024-10-01")
    call_command("purge_log_records", args)
    captured = capsys.readouterr()

    assert captured.out == "No records has been found for purging.\n"

    args = ("--activation-name", "na", "--date", "2024-10-01")
    call_command("purge_log_records", args)
    captured = capsys.readouterr()
    assert captured.out == "No records has been found for purging.\n"


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

    call_command(command, args)

    captured = capsys.readouterr()

    if cutoff_days < 10:
        assert models.RulebookProcessLog.objects.count() == 4

        for log_record in models.RulebookProcessLog.objects.all():
            assert (
                f"All log records older than {date_str} are purged at"
                in log_record.log
            )
    else:
        assert models.RulebookProcessLog.objects.count() == 6

        for log_record in models.RulebookProcessLog.objects.filter(
            activation_instance__activation=activations[0]
        ):
            assert (
                f"All log records older than {date_str} are purged at"
                in log_record.log
            )

        for log_record in models.RulebookProcessLog.objects.filter(
            activation_instance__activation=activations[1]
        ):
            assert (
                f"All log records older than {date_str} are purged at"
                not in log_record.log
            )

    assert f"Log records older than {date_str} are purged." in captured.out
