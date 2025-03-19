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
import csv
import io
import json
import logging
import os
import tarfile
import tempfile
import uuid
from datetime import timedelta
from typing import IO, List
from unittest.mock import MagicMock, patch

import pytest
from django.db import DatabaseError
from django.db.models.query import QuerySet
from django.utils.timezone import now
from insights_analytics_collector import Collector

from aap_eda.analytics import analytics_collectors as collectors
from aap_eda.analytics.analytics_collectors import _copy_table, config
from aap_eda.analytics.collector import AnalyticsCollector
from aap_eda.conf import settings_registry
from aap_eda.core import enums, models


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()
    return None


@pytest.fixture
def activations_with_different_status(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
) -> List[models.Activation]:
    """Return Activations"""
    activation_data = [
        {
            "name": "pending-activation",
            "description": "Activation in pending state",
            "status": enums.ActivationStatus.PENDING,
            "log_level": "info",
        },
        {
            "name": "running-activation",
            "description": "Activation in running state",
            "status": enums.ActivationStatus.RUNNING,
            "log_level": "error",
        },
        {
            "name": "completed-activation",
            "description": "Activation in completed state",
            "status": enums.ActivationStatus.COMPLETED,
            "log_level": "debug",
        },
    ]

    activations = [
        models.Activation(
            name=data["name"],
            description=data["description"],
            status=data["status"],
            decision_environment=default_decision_environment,
            project=default_project,
            rulebook=default_rulebook,
            extra_var=default_extra_var_data,
            organization=default_organization,
            user=default_user,
            log_level=data["log_level"],
        )
        for data in activation_data
    ]
    return models.Activation.objects.bulk_create(activations)


@pytest.fixture
def mock_queryset():
    qs = MagicMock(spec=QuerySet)
    qs.query.sql_with_params.return_value = ("SELECT * FROM test_table", ())
    return qs


@pytest.mark.parametrize(
    "env_vars, expected_type",
    [
        # OpenShift
        ({"container": "oci"}, "openshift"),
        ({"container": "oci", "OTHER_VAR": "value"}, "openshift"),
        # Kubernetes
        ({"KUBERNETES_SERVICE_PORT": "443"}, "k8s"),
        ({"KUBERNETES_SERVICE_PORT": "80", "container": "docker"}, "k8s"),
        # traditional
        ({}, "traditional"),
        ({"PATH": "/usr/bin"}, "traditional"),
        # corner cases
        ({"container": "podman"}, "traditional"),
    ],
)
@pytest.mark.django_db
def test_install_type_detection(env_vars, expected_type):
    with patch.dict(os.environ, env_vars, clear=True):
        result = config()
        assert (
            result["platform"]["type"] == expected_type
        ), f"Failed for env: {env_vars}"


@pytest.mark.django_db
def test_internal_infra_files():
    collector = AnalyticsCollector(
        collection_type=Collector.DRY_RUN, collector_module=collectors
    )
    until = now()
    time_start = until - timedelta(hours=9)

    tgz_files = collector.gather(since=time_start, until=until)

    assert len(tgz_files) == 1

    files = {}
    with tarfile.open(tgz_files[0], "r:gz") as archive:
        for member in archive.getmembers():
            files[member.name] = archive.extractfile(member)

        assert "./config.json" in files
        assert "./manifest.json" in files
        assert "./data_collection_status.csv" in files

        config_json = json.loads(files["./config.json"].read())
        manifest_json = json.loads(files["./manifest.json"].read())
        data_collection_status_csv = io.BytesIO(
            files["./data_collection_status.csv"].read()
        )
        data_collection_status = io.TextIOWrapper(
            data_collection_status_csv, encoding="utf-8"
        )

        assert len(config_json.keys()) == 4
        for key in config_json.keys():
            assert key in [
                "install_uuid",
                "platform",
                "eda_log_level",
                "eda_version",
            ]
        assert manifest_json["config.json"] == "1.0"
        assert manifest_json["data_collection_status.csv"] == "1.0"

        reader = csv.reader(data_collection_status)
        header = next(reader)
        lines = list(reader)

        assert header == [
            "collection_start_timestamp",
            "since",
            "until",
            "file_name",
            "status",
            "elapsed",
        ]
        assert len(lines) == 3

    collector._gather_cleanup()


@pytest.mark.django_db
def test_jobs_stats_collector(
    default_activation: models.Activation,
    audit_action_1: models.AuditAction,
    audit_action_2: models.AuditAction,
    audit_action_3: models.AuditAction,
):
    until = now()
    time_start = until - timedelta(hours=9)
    job_ids = ["8018", "8020"]
    intall_uuids = [str(uuid.uuid4()), str(uuid.uuid4())]
    audit_action_1.url = (
        f"https://controller_1/#/jobs/playbook/{job_ids[0]}/details/"
    )
    audit_action_2.url = (
        f"https://controller_2/#/jobs/workflow/{job_ids[0]}/details/"
    )
    audit_action_3.url = (
        f"https://controller_1/#/jobs/workflow/{job_ids[1]}/details/"
    )
    audit_action_1.save(update_fields=["url"])
    audit_action_2.save(update_fields=["url"])
    audit_action_3.save(update_fields=["url"])

    with patch(
        "aap_eda.analytics.analytics_collectors.collect_controllers_info"
    ) as collect_controllers_info:
        collect_controllers_info.return_value = {
            "https://controller_1/": {"install_uuid": intall_uuids[0]},
            "https://controller_2/": {"install_uuid": intall_uuids[1]},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data = collectors.jobs_stats(
                time_start, tmpdir, until=now() + timedelta(seconds=1)
            )
            assert list(data.keys()) == job_ids

            first_jobs = data[job_ids[0]]
            assert len(first_jobs) == 2
            assert first_jobs[0]["job_id"] == job_ids[0]
            assert first_jobs[0]["type"] == "run_job_template"
            assert first_jobs[0]["created_at"] == audit_action_1.fired_at
            assert first_jobs[0]["status"] == audit_action_1.status
            assert first_jobs[0]["url"] == audit_action_1.url
            assert first_jobs[0]["install_uuid"] == intall_uuids[0]

            assert first_jobs[1]["job_id"] == job_ids[0]
            assert first_jobs[1]["type"] == "run_workflow_template"
            assert first_jobs[1]["created_at"] == audit_action_2.fired_at
            assert first_jobs[1]["status"] == audit_action_2.status
            assert first_jobs[1]["url"] == audit_action_2.url
            assert first_jobs[1]["install_uuid"] == intall_uuids[1]

            second_jobs = data[job_ids[1]]
            assert len(second_jobs) == 1
            assert second_jobs[0]["job_id"] == job_ids[1]
            assert second_jobs[0]["type"] == "run_workflow_template"
            assert second_jobs[0]["created_at"] == audit_action_3.fired_at
            assert second_jobs[0]["status"] == audit_action_3.status
            assert second_jobs[0]["url"] == audit_action_3.url
            assert second_jobs[0]["install_uuid"] == intall_uuids[0]


@pytest.mark.django_db
def test_activations_sources(
    default_activation: models.Activation,
    new_activation: models.Activation,
    default_event_streams: List[models.EventStream],
):
    until = now()
    time_start = until - timedelta(hours=9)

    for stream in default_event_streams:
        default_activation.event_streams.add(stream.id)

    with tempfile.TemporaryDirectory() as tmpdir:
        data = collectors.activation_sources(time_start, tmpdir, until)

        assert data["ansible.eda.range"]["occurrence"] == 3
        assert sorted(data["ansible.eda.range"]["activation_ids"]) == sorted(
            [default_activation.id, new_activation.id]
        )
        assert sorted(data["ansible.eda.range"]["event_stream_ids"]) == sorted(
            [default_event_streams[0].id, default_event_streams[1].id]
        )
        assert data["ansible.eda.range"]["event_streams"]["hmac"] == 2


@pytest.mark.django_db
def test_activations_stats(
    default_activation_instances: List[models.RulebookProcess],
    default_activation: models.Activation,
    new_activation: models.Activation,
):
    until = now()
    time_start = until - timedelta(hours=9)

    default_activation.restart_count = 1
    default_activation.failure_count = 2
    default_activation.save(update_fields=["restart_count", "failure_count"])
    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.activations_stats_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "activations_stats_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "name",
                "status",
                "restart_count",
                "failure_count",
                "log_level",
                "organization_id",
                "created_at",
                "ended_at",
                "activations_counts",
                "max_restart_count",
            ]
            assert len(lines) == 2
            assert lines[0][0] == f"{new_activation.id}"
            assert lines[0][1] == new_activation.name
            assert lines[0][2] == new_activation.status
            assert int(lines[0][3]) == new_activation.restart_count
            assert int(lines[0][4]) == new_activation.failure_count
            assert lines[0][8].split("+")[
                0
            ] == new_activation.modified_at.isoformat(" ").split("+")[
                0
            ].rstrip(
                "0"
            )
            assert int(lines[0][9]) == 0
            assert lines[1][0] == f"{default_activation.id}"
            assert lines[1][1] == default_activation.name
            assert lines[1][2] == default_activation.status
            assert int(lines[1][3]) == default_activation.restart_count
            assert int(lines[1][4]) == default_activation.failure_count
            assert lines[1][8] == ""
            assert int(lines[1][9]) == 2


@pytest.mark.django_db
def test_activations_table_collector(default_activation: models.Activation):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.activations_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "activations_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "description",
                "is_enabled",
                "git_hash",
                "decision_environment_id",
                "project_id",
                "rulebook_id",
                "extra_var",
                "restart_policy",
                "status",
                "current_job_id",
                "restart_count",
                "failure_count",
                "is_valid",
                "rulebook_name",
                "rulebook_rulesets",
                "ruleset_stats",
                "created_at",
                "modified_at",
                "status_updated_at",
                "status_message",
                "latest_instance_id",
                "log_level",
                "eda_system_vault_credential_id",
                "k8s_service_name",
                "source_mappings",
                "skip_audit_events",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_activation.id)
            assert lines[0][2] == default_activation.name
            assert lines[0][3] == default_activation.description


def assert_audit_rules(expected_audit_rules):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.audit_rules_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "audit_rules_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "status",
                "created_at",
                "fired_at",
                "rule_uuid",
                "ruleset_uuid",
                "ruleset_name",
                "job_instance_id",
                "activation_instance_id",
            ]
            assert len(lines) == len(expected_audit_rules)
            for i, rule in enumerate(expected_audit_rules):
                assert lines[i][0] == str(rule.id)
                assert lines[i][2] == rule.name
                assert lines[i][3] == rule.status


@pytest.mark.django_db
def test_single_audit_rule_table_collector(
    default_audit_rule: models.AuditRule,
):
    assert_audit_rules([default_audit_rule])


@pytest.mark.django_db
def test_multiple_audit_rules_table_collector(
    audit_rule_1: models.AuditRule,
    audit_rule_2: models.AuditRule,
):
    assert_audit_rules([audit_rule_1, audit_rule_2])


@pytest.mark.django_db
def test_single_audit_action_table_collector(
    audit_action_1: models.AuditAction,
    audit_event_1: models.AuditEvent,
):
    assert_audit_actions([audit_action_1])
    assert_audit_events([audit_event_1])


@pytest.mark.django_db
def test_multiple_audit_action_table_collector(
    audit_action_1: models.AuditAction,
    audit_action_2: models.AuditAction,
    audit_action_3: models.AuditAction,
    audit_event_1: models.AuditEvent,
    audit_event_2: models.AuditEvent,
):
    assert_audit_actions([audit_action_1, audit_action_2, audit_action_3])
    assert_audit_events([audit_event_1, audit_event_2])


def assert_audit_actions(expected_audit_actions):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.audit_actions_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "audit_actions_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "name",
                "status",
                "url",
                "fired_at",
                "rule_fired_at",
                "status_message",
                "audit_rule_id",
            ]
            assert len(lines) == len(expected_audit_actions)
            assert sorted([line[0] for line in lines]) == sorted(
                [action.id for action in expected_audit_actions]
            )


def assert_audit_events(expected_audit_events):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.audit_events_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "audit_events_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "source_name",
                "source_type",
                "received_at",
                "rule_fired_at",
            ]
            assert len(lines) == len(expected_audit_events)
            assert sorted([line[0] for line in lines]) == sorted(
                [event.id for event in expected_audit_events]
            )


@pytest.mark.django_db
def test_empty_audit_event_returns_empty():
    until = now()
    time_start = until - timedelta(hours=9)
    mock_audit_event_query = MagicMock(spec=QuerySet)
    mock_audit_event_query.values.return_value.exists.return_value = False

    with patch(
        "aap_eda.analytics.analytics_collectors._get_audit_action_qs",
        return_value=MagicMock(exists=lambda: True),
    ), patch(
        "aap_eda.analytics.analytics_collectors._get_audit_event_query",
        return_value=mock_audit_event_query,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collectors.audit_events_table(
                time_start, tmpdir, until=now() + timedelta(seconds=1)
            )

            assert result == []


@pytest.mark.django_db
def test_eda_credentials_table_collector(
    default_eda_credential: models.EdaCredential,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.eda_credentials_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "eda_credentials_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "description",
                "managed",
                "created_at",
                "modified_at",
                "credential_type_id",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_eda_credential.id)
            assert lines[0][2] == default_eda_credential.name
            assert lines[0][3] == default_eda_credential.description


@pytest.mark.django_db
def test_credential_types_table_collector(
    default_credential_type: models.CredentialType,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.credential_types_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "credential_types_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "name",
                "description",
                "inputs",
                "injectors",
                "managed",
                "kind",
                "namespace",
                "created_at",
                "modified_at",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_credential_type.id)
            assert lines[0][1] == default_credential_type.name
            assert lines[0][2] == default_credential_type.description


@pytest.mark.django_db
def test_decision_environments_table_collector(
    default_decision_environment: models.DecisionEnvironment,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.decision_environments_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(
            os.path.join(tmpdir, "decision_environments_table.csv")
        ) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "description",
                "image_url",
                "eda_credential_id",
                "created_at",
                "modified_at",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_decision_environment.id)
            assert lines[0][2] == default_decision_environment.name
            assert lines[0][3] == default_decision_environment.description


@pytest.mark.django_db
def test_event_streams_table_collector(
    default_event_stream: models.EventStream,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.event_streams_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "event_streams_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "event_stream_type",
                "eda_credential_id",
                "uuid",
                "created_at",
                "modified_at",
                "events_received",
                "last_event_received_at",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_event_stream.id)
            assert lines[0][2] == default_event_stream.name
            assert lines[0][3] == default_event_stream.event_stream_type


@pytest.mark.django_db
def test_event_streams_table_by_activation_collector(
    default_activation: models.Activation,
    new_activation: models.Activation,
    default_event_streams: list[models.EventStream],
):
    default_activation.event_streams.add(default_event_streams[0])
    new_activation.event_streams.add(default_event_streams[1])

    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.event_streams_by_activation_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(
            os.path.join(tmpdir, "event_streams_by_activation_table.csv")
        ) as f:
            assert_event_streams_data(
                default_event_streams, [default_activation, new_activation], f
            )


@pytest.mark.django_db
def test_event_streams_table_by_running_activations_collector(
    activations_with_different_status: list[models.Activation],
    default_event_streams: list[models.EventStream],
):
    activations_with_different_status[0].event_streams.add(
        default_event_streams[0]
    )
    activations_with_different_status[1].event_streams.add(
        default_event_streams[1]
    )

    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.event_streams_by_running_activations_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(
            os.path.join(
                tmpdir, "event_streams_by_running_activations_table.csv"
            )
        ) as f:
            assert_event_streams_data(
                default_event_streams, activations_with_different_status, f
            )


def assert_event_streams_data(
    default_event_streams: list[models.EventStream],
    activations: list[models.Activation],
    data: IO[str],
):
    reader = csv.reader(data)

    header = next(reader)
    lines = list(reader)

    assert header == [
        "name",
        "event_stream_type",
        "eda_credential_id",
        "events_received",
        "last_event_received_at",
        "organization_id",
        "event_stream_id",
        "activation_id",
    ]
    assert len(lines) == 2
    assert lines[0][0] == default_event_streams[0].name
    assert lines[0][1] == default_event_streams[0].event_stream_type
    assert lines[0][6] == str(default_event_streams[0].id)
    assert lines[1][0] == default_event_streams[1].name
    assert lines[1][1] == default_event_streams[1].event_stream_type
    assert lines[1][6] == str(default_event_streams[1].id)
    assert sorted([lines[0][7], lines[1][7]]) == sorted(
        [
            str(activations[0].id),
            str(activations[1].id),
        ]
    )


@pytest.mark.django_db
def test_projects_table_collector(
    default_project: models.Project,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.projects_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "projects_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "description",
                "url",
                "proxy",
                "git_hash",
                "verify_ssl",
                "eda_credential_id",
                "archive_file",
                "import_state",
                "import_task_id",
                "import_error",
                "created_at",
                "modified_at",
                "scm_type",
                "scm_branch",
                "scm_refspec",
                "signature_validation_credential_id",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_project.id)
            assert lines[0][2] == default_project.name
            assert lines[0][3] == default_project.description


@pytest.mark.django_db
def test_rulebooks_table_collector(
    default_rulebook: models.Rulebook,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.rulebooks_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "rulebooks_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "description",
                "rulesets",
                "project_id",
                "created_at",
                "modified_at",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_rulebook.id)
            assert lines[0][2] == default_rulebook.name
            assert lines[0][3] == default_rulebook.description


@pytest.mark.django_db
def test_rulebook_processes_table_collector(
    default_activation_instance: models.RulebookProcess,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.rulebook_processes_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "rulebook_processes_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "organization_id",
                "name",
                "status",
                "git_hash",
                "activation_id",
                "parent_type",
                "started_at",
                "updated_at",
                "ended_at",
                "activation_pod_id",
                "status_message",
                "log_read_at",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_activation_instance.id)
            assert lines[0][2] == default_activation_instance.name
            assert lines[0][3] == default_activation_instance.status


@pytest.mark.django_db
def test_organizations_table_collector(
    default_organization: models.Organization,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.organizations_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "organizations_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "modified",
                "created",
                "name",
                "description",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_organization.id)
            assert lines[0][3] == default_organization.name
            assert lines[0][4] == default_organization.description


@pytest.mark.django_db
def test_teams_table_collector(
    default_team: models.Team,
):
    until = now()
    time_start = until - timedelta(hours=9)

    with tempfile.TemporaryDirectory() as tmpdir:
        collectors.teams_table(
            time_start, tmpdir, until=now() + timedelta(seconds=1)
        )
        with open(os.path.join(tmpdir, "teams_table.csv")) as f:
            reader = csv.reader(f)

            header = next(reader)
            lines = list(reader)

            assert header == [
                "id",
                "modified",
                "created",
                "name",
                "description",
                "organization_id",
            ]
            assert len(lines) == 1
            assert lines[0][0] == str(default_team.id)
            assert lines[0][3] == default_team.name
            assert lines[0][4] == default_team.description


@pytest.mark.django_db
def test_database_error_propagation(tmp_path, mock_queryset, caplog_factory):
    logger = logging.getLogger("aap_eda.analytics")
    eda_log = caplog_factory(logger)

    with patch("django.db.connection.cursor") as mock_cursor:
        mock_cursor.return_value.__enter__.return_value.execute.side_effect = (
            DatabaseError("View creation failed")
        )

        result = _copy_table("test", mock_queryset, str(tmp_path))

        assert result is None
        assert "Database error occurred: View creation failed" in eda_log.text


@pytest.mark.django_db
def test_copy_operation_failure(tmp_path, mock_queryset, caplog_factory):
    logger = logging.getLogger("aap_eda.analytics")
    eda_log = caplog_factory(logger)

    mock_copy = MagicMock()
    mock_copy.read.side_effect = DatabaseError("COPY stream broken")

    with patch("django.db.connection.cursor") as mock_cursor:
        ctx = mock_cursor.return_value.__enter__.return_value
        ctx.copy.return_value.__enter__.return_value = mock_copy

        result = _copy_table("test", mock_queryset, str(tmp_path))

        assert result is None
        assert "COPY stream broken" in eda_log.text


@pytest.mark.parametrize(
    "exception,expected_log",
    [
        (DatabaseError("Connection lost"), "Database error occurred"),
        (OSError("Permission denied"), "File I/O error occurred"),
        (MemoryError(), "An unexpected error occurred"),
    ],
)
@pytest.mark.django_db
def test_error_handling_scenarios(
    exception, expected_log, tmp_path, mock_queryset, caplog_factory
):
    logger = logging.getLogger("aap_eda.analytics")
    eda_log = caplog_factory(logger)

    with patch(
        "aap_eda.analytics.analytics_collectors.connection.cursor"
    ) as mock_cursor:
        mock_cursor.return_value.__enter__.return_value.execute.side_effect = (
            exception
        )

        result = _copy_table("test", mock_queryset, str(tmp_path))

        assert result is None
        assert expected_log in eda_log.text


@pytest.mark.django_db
def test_view_cleanup(tmp_path, mock_queryset):
    mock_copy = MagicMock()
    mock_copy.read.side_effect = [
        "COPY stream broken\n".encode(),
        "".encode(),
    ]

    with patch("django.db.connection.cursor") as mock_cursor:
        ctx = mock_cursor.return_value.__enter__.return_value
        ctx.copy.return_value.__enter__.return_value = mock_copy
        mock_execute = mock_cursor.return_value.__enter__.return_value.execute

        _copy_table("test", mock_queryset, str(tmp_path))

        drop_calls = [
            call[0][0]
            for call in mock_execute.call_args_list
            if "DROP VIEW" in call[0][0]
        ]
        assert len(drop_calls) == 1
        assert "IF EXISTS" in drop_calls[0]
