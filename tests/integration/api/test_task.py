#  Copyright 2023 Red Hat, Inc.
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
import uuid
from datetime import datetime
from typing import Any, Optional, Union
from unittest import mock

from rest_framework import status
from rest_framework.test import APIClient
from rq.job import JobStatus

from tests.integration.constants import api_url_v1


@mock.patch("aap_eda.api.views.tasks.list_jobs")
def test_list_tasks(list_jobs: mock.Mock, client: APIClient):
    list_jobs.return_value = [
        _create_job(
            "6636aad2-7998-4376-bb4d-ef19796fd1b3",
            JobStatus.QUEUED,
            created_at="2023-01-25T15:24:45.148282",
            enqueued_at="2023-01-25T15:24:47.123923",
        ),
        _create_job(
            "3992e416-b0f5-4e2e-8ae1-432bcdbc3de3",
            JobStatus.FINISHED,
            created_at="2023-01-25T15:25:19.220850",
            enqueued_at="2023-01-25T15:25:19.804863",
            started_at="2023-01-25T15:25:21.572900",
            ended_at="2023-01-25T15:25:22.284716",
            result={
                "obj_id": 42,
            },
        ),
    ]
    response = client.get(f"{api_url_v1}/tasks/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == [
        {
            "id": "6636aad2-7998-4376-bb4d-ef19796fd1b3",
            "status": "queued",
            "created_at": "2023-01-25T15:24:45.148282Z",
            "enqueued_at": "2023-01-25T15:24:47.123923Z",
            "started_at": None,
            "finished_at": None,
            "result": None,
        },
        {
            "id": "3992e416-b0f5-4e2e-8ae1-432bcdbc3de3",
            "status": "finished",
            "created_at": "2023-01-25T15:25:19.220850Z",
            "enqueued_at": "2023-01-25T15:25:19.804863Z",
            "started_at": "2023-01-25T15:25:21.572900Z",
            "finished_at": "2023-01-25T15:25:22.284716Z",
            "result": {"obj_id": 42},
        },
    ]


@mock.patch("aap_eda.api.views.tasks.get_job")
def test_retrieve_task(get_job: mock.Mock, client: APIClient):
    get_job.return_value = _create_job(
        "6636aad2-7998-4376-bb4d-ef19796fd1b3",
        JobStatus.QUEUED,
        created_at="2023-01-25T15:24:45.148282",
        enqueued_at="2023-01-25T15:24:47.123923",
    )
    response = client.get(
        f"{api_url_v1}/tasks/6636aad2-7998-4376-bb4d-ef19796fd1b3/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "id": "6636aad2-7998-4376-bb4d-ef19796fd1b3",
        "status": "queued",
        "created_at": "2023-01-25T15:24:45.148282Z",
        "enqueued_at": "2023-01-25T15:24:47.123923Z",
        "started_at": None,
        "finished_at": None,
        "result": None,
    }


@mock.patch("aap_eda.api.views.tasks.get_job")
def test_retrieve_task_not_exists(get_job: mock.Mock, client: APIClient):
    get_job.return_value = None
    response = client.get(
        f"{api_url_v1}/tasks/a13f539c-aaa1-46b6-80c3-7dbfad941292/"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def _parse_datetime(date_string: Optional[str]) -> Optional[datetime]:
    if date_string is None:
        return None
    return datetime.fromisoformat(date_string)


def _create_job(
    id_: Union[str, uuid.UUID],
    status: JobStatus,
    *,
    created_at: Optional[str] = None,
    enqueued_at: Optional[str] = None,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
    result: Any = None,
) -> mock.Mock:
    job = mock.Mock()
    job.id = id_
    job.result = result

    job.get_status.return_value = status.value

    job.created_at = _parse_datetime(created_at)
    job.enqueued_at = _parse_datetime(enqueued_at)
    job.started_at = _parse_datetime(started_at)
    job.ended_at = _parse_datetime(ended_at)

    return job
