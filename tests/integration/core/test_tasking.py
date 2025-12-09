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


import pytest

from aap_eda.core.tasking import logger, unique_enqueue


@pytest.fixture
def eda_caplog(caplog_factory):
    return caplog_factory(logger)


def fake_task(number: int):
    pass


@pytest.mark.django_db
def test_unique_enqueue_existing_job(default_queue, eda_caplog):
    # With dispatcherd, unique_enqueue simply submits tasks without returning
    # job objects
    # Test that the function executes without error
    default_queue.enqueue(fake_task, job_id="fake_task", number=1)
    result = unique_enqueue(
        default_queue.name, "fake_task", fake_task, number=2
    )
    assert result is None  # dispatcherd functions return None


@pytest.mark.django_db
def test_unique_enqueue_old_job_completed(default_queue, eda_caplog):
    # With dispatcherd, job status tracking is handled differently
    # Test that the function executes without error
    old_job = default_queue.enqueue(fake_task, job_id="fake_task", number=1)
    old_job.set_status("finished")
    result = unique_enqueue(
        default_queue.name, "fake_task", fake_task, number=2
    )
    assert result is None  # dispatcherd functions return None


@pytest.mark.django_db
def test_unique_enqueue_old_job_failed(default_queue, eda_caplog):
    # With dispatcherd, job status tracking is handled differently
    # Test that the function executes without error
    old_job = default_queue.enqueue(fake_task, job_id="fake_task", number=1)
    old_job.set_status("failed")
    result = unique_enqueue(
        default_queue.name, "fake_task", fake_task, number=2
    )
    assert result is None  # dispatcherd functions return None


@pytest.mark.django_db
def test_unique_enqueue_new_job(default_queue, eda_caplog):
    # With dispatcherd, unique_enqueue simply submits tasks without returning
    # job objects
    # Test that the function executes without error
    result = unique_enqueue(
        default_queue.name, "fake_task", fake_task, number=2
    )
    assert result is None  # dispatcherd functions return None
