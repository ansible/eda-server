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

from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.core.tasking import DefaultWorker, Queue
from aap_eda.tasks.project import monitor_project_tasks


def fake_job():
    pass


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.import_project")
def test_monitor_project_tasks_import(
    import_task_mock: mock.Mock,
    default_queue: Queue,
):
    """Test monitor_project_tasks rq task.

    Test that monitor_project_tasks recreate the task
    when import project task is stuck.
    """
    job_id = "b93ae0b6-53fe-11ee-a5c4-482ae389cd08"
    job = mock.Mock(id=job_id)
    import_task_mock.delay.return_value = job

    project = models.Project.objects.create(
        name="test_monitor_project_tasks",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.PENDING,
    )
    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker([default_queue], connection=default_queue.connection)
    worker.work(burst=True)
    project.refresh_from_db()
    assert str(project.import_task_id) == job_id


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.sync_project")
def test_monitor_project_tasks_sync(
    sync_task_mock: mock.Mock,
    default_queue: Queue,
):
    """Test monitor_project_tasks rq task.

    Test that monitor_project_tasks recreate the task
    when sync project task is stuck.
    """
    job_id = "b93ae0b6-53fe-11ee-a5c4-482ae389cd08"
    job = mock.Mock(id=job_id)
    sync_task_mock.delay.return_value = job

    project = models.Project.objects.create(
        name="test_monitor_project_tasks",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.PENDING,
        git_hash="dummy-hash",
    )
    default_queue.enqueue(monitor_project_tasks, default_queue.name)

    worker = DefaultWorker([default_queue], connection=default_queue.connection)
    worker.work(burst=True)
    project.refresh_from_db()
    assert str(project.import_task_id) == job_id


@pytest.mark.django_db
@mock.patch("aap_eda.tasks.project.sync_project")
def test_monitor_project_tasks_with_job(
    sync_task_mock: mock.Mock,
    default_queue: Queue,
):
    """Test monitor_project_tasks rq task.

    Test that monitor_project_tasks does not recreate the task
    when sync project task is not stuck
    """
    job_id = "b93ae0b6-53fe-11ee-a5c4-482ae389cd08"
    job = mock.Mock(id=job_id)
    sync_task_mock.delay.return_value = job
    expected_job_id = "13affe8a-5401-11ee-8f1c-482ae389cd08"

    project = models.Project.objects.create(
        name="test_monitor_project_tasks",
        url="https://git.example.com/acme/project-01",
        import_state=models.Project.ImportState.PENDING,
        git_hash="dummy-hash",
        import_task_id=expected_job_id,
    )
    default_queue.enqueue(fake_job, job_id=expected_job_id)
    default_queue.enqueue(monitor_project_tasks)

    worker = DefaultWorker([default_queue], connection=default_queue.connection)
    worker.work(burst=True)
    project.refresh_from_db()
    assert str(project.import_task_id) == expected_job_id
