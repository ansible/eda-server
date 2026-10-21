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
def test_superuser_queues_global_purge_on_default_queue(superuser_client):
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
                "audit_trail": True,
                "activation_ids": [12, 13],
                "activation_names": ["production"],
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
            "activation-ids": [12, 13],
            "activation-names": ["production"],
        },
    )


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
        {"retention_duration": "not-a-duration"},
        {"retention_duration": "P0D"},
        {"retention_duration": "-P1D"},
        {"before_date": "2026-01-01"},
        {"activation_ids": [0]},
        {"activation_ids": []},
        {"activation_names": [""]},
        {"activation_names": ["   "]},
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
def test_enqueue_failure_is_not_reported_as_accepted(superuser_client):
    with mock.patch(
        "aap_eda.tasks.management.submit_task",
        side_effect=RuntimeError("queue unavailable"),
    ):
        response = superuser_client.post(PURGE_URL, {}, format="json")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data == {"detail": "Unable to queue log purge job."}
