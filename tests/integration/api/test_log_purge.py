#  Copyright 2026 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0

from unittest import mock
from uuid import UUID

import pytest
from rest_framework import status

from aap_eda.tasks.management import LOG_PURGE_TASK_TIMEOUT_SECONDS
from tests.integration.constants import api_url_v1

PURGE_URL = f"{api_url_v1}/logs/purge/"
JOB_ID = UUID("c3dd8dd8-b1d5-49e0-86e9-216cb2c942a8")


@pytest.mark.django_db
def test_superuser_queues_scoped_purge_with_one_eda_job_id(
    superuser_client, default_activation, new_activation
):
    with mock.patch(
        "aap_eda.tasks.management.uuid4", return_value=JOB_ID
    ), mock.patch(
        "aap_eda.tasks.management.submit_task",
        return_value=({"uuid": str(JOB_ID)}, "default"),
    ) as submit_task:
        response = superuser_client.post(
            PURGE_URL,
            {
                "retention_duration": "P30D",
                "activation_ids": [default_activation.id],
                "activation_names": [new_activation.name],
            },
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data == {"job_id": str(JOB_ID)}
    submit_task.assert_called_once()
    (task,) = submit_task.call_args.args
    options = submit_task.call_args.kwargs
    assert task.__name__ == "_aap_eda_manage"
    assert options["queue"] == "default"
    assert options["timeout"] == LOG_PURGE_TASK_TIMEOUT_SECONDS
    assert options["uuid"] == str(JOB_ID)
    assert options["args"] == (
        str(JOB_ID),
        "purge_log_records",
        {
            "retention_duration": "P30D",
            "audit_trail": True,
            "activation-ids": sorted(
                [default_activation.id, new_activation.id]
            ),
            "internal-job-uuid": str(JOB_ID),
        },
    )


@pytest.mark.django_db
def test_name_only_scope_is_queued_as_activation_id(
    superuser_client, default_activation
):
    with mock.patch(
        "aap_eda.tasks.management.submit_task",
        return_value=({"uuid": str(JOB_ID)}, "default"),
    ) as submit_task:
        response = superuser_client.post(
            PURGE_URL,
            {
                "before_date": "2020-01-01",
                "activation_names": [default_activation.name],
            },
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    options = submit_task.call_args.kwargs["args"][2]
    assert options["activation-ids"] == [default_activation.id]
    assert "activation-names" not in options


@pytest.mark.django_db
def test_superuser_queues_global_purge_with_absolute_date(superuser_client):
    with mock.patch(
        "aap_eda.tasks.management.uuid4", return_value=JOB_ID
    ), mock.patch(
        "aap_eda.tasks.management.submit_task",
        return_value=({"uuid": str(JOB_ID)}, "default"),
    ) as submit_task:
        response = superuser_client.post(
            PURGE_URL, {"before_date": "2020-01-01"}, format="json"
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data == {"job_id": str(JOB_ID)}
    assert submit_task.call_args.kwargs["args"][2] == {
        "date": "2020-01-01",
        "audit_trail": True,
        "internal-job-uuid": str(JOB_ID),
    }


@pytest.mark.django_db
def test_superuser_queues_purge_all_logs_without_cutoff(superuser_client):
    with mock.patch(
        "aap_eda.tasks.management.uuid4", return_value=JOB_ID
    ), mock.patch(
        "aap_eda.tasks.management.submit_task",
        return_value=({"uuid": str(JOB_ID)}, "default"),
    ) as submit_task:
        response = superuser_client.post(
            PURGE_URL, {"purge-all-logs": True}, format="json"
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data == {"job_id": str(JOB_ID)}
    assert submit_task.call_args.kwargs["args"] == (
        str(JOB_ID),
        "purge_log_records",
        {
            "audit_trail": True,
            "purge-all-logs": True,
            "internal-job-uuid": str(JOB_ID),
        },
    )


@pytest.mark.django_db
def test_api_keeps_activation_scope_when_audit_is_disabled(
    superuser_client, default_activation
):
    with mock.patch(
        "aap_eda.tasks.management.uuid4", return_value=JOB_ID
    ), mock.patch(
        "aap_eda.tasks.management.submit_task",
        return_value=({"uuid": str(JOB_ID)}, "default"),
    ) as submit_task:
        response = superuser_client.post(
            PURGE_URL,
            {
                "before_date": "2020-01-01",
                "activation_ids": [default_activation.id],
                "audit_trail": False,
            },
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert submit_task.call_args.kwargs["args"][2] == {
        "date": "2020-01-01",
        "audit_trail": False,
        "activation-ids": [default_activation.id],
        "internal-job-uuid": str(JOB_ID),
    }


@pytest.mark.django_db
def test_purge_requires_superuser(admin_client):
    response = admin_client.post(PURGE_URL, {}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_anonymous_purge_uses_api_permission_denial(base_client):
    response = base_client.post(PURGE_URL, {}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"before_date": "2999-01-01"},
        {"before_date": "not-a-date"},
        {"before_date": "2020-01-01", "retention_duration": "P30D"},
        {"retention_duration": "not-a-duration"},
        {"retention_duration": "P0D"},
        {"retention_duration": "-P1D"},
        {"purge-all-logs": False},
        {"purge_all_logs": True},
        {"purge-all-logs": True, "before_date": "2020-01-01"},
        {"purge-all-logs": True, "retention_duration": "P30D"},
        {"purge-all-logs": True, "audit_trail": False},
        {"purge-all-logs": True, "activation_ids": [1]},
        {"purge-all-logs": True, "activation_names": ["example"]},
        {"before_date": "2020-01-01", "activation_ids": [0]},
        {"before_date": "2020-01-01", "activation_ids": []},
        {"before_date": "2020-01-01", "activation_names": [""]},
        {"before_date": "2020-01-01", "activation_names": ["   "]},
        {"before_date": "2020-01-01", "activation_ids": [99999999]},
        {"before_date": "2020-01-01", "activation_id": 1},
        {"before_date": "2020-01-01", "activation_id": "invalid"},
        {"before_date": "2020-01-01", "activation_id": None},
        {"before_date": "2020-01-01", "activation_namess": ["demo"]},
        {
            "before_date": "2020-01-01",
            "activation_names": ["missing-activation"],
        },
    ],
)
def test_invalid_purge_request_is_rejected_before_enqueue(
    superuser_client, payload
):
    with mock.patch("aap_eda.tasks.management.submit_task") as submit_task:
        response = superuser_client.post(PURGE_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    submit_task.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_kind", ["id", "name"])
def test_mixed_valid_and_unknown_scope_never_queues(
    superuser_client, default_activation, invalid_kind
):
    payload = {
        "before_date": "2020-01-01",
        "activation_ids": [default_activation.id],
    }
    if invalid_kind == "id":
        payload["activation_ids"].append(default_activation.id + 99999999)
    else:
        payload["activation_names"] = ["missing-activation"]

    with mock.patch("aap_eda.tasks.management.submit_task") as submit_task:
        response = superuser_client.post(PURGE_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    submit_task.assert_not_called()


@pytest.mark.django_db
def test_enqueue_failure_is_not_reported_as_accepted(superuser_client):
    with mock.patch(
        "aap_eda.tasks.management.submit_task",
        side_effect=RuntimeError("queue unavailable"),
    ):
        response = superuser_client.post(
            PURGE_URL, {"before_date": "2020-01-01"}, format="json"
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data == {"detail": "Unable to queue log purge job."}
