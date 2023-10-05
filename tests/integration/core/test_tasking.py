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


import logging

import pytest

from aap_eda.core.tasking import logger, unique_enqueue


@pytest.fixture
def eda_caplog(caplog):
    logger.setLevel(logging.INFO)
    logger.handlers += [caplog.handler]
    return caplog


def fake_task(number: int):
    pass


def test_unique_enqueue_existing_job(default_queue, eda_caplog):
    default_queue.enqueue(fake_task, job_id="fake_task", number=1)
    job = unique_enqueue(default_queue.name, "fake_task", fake_task, number=2)
    assert job.kwargs["number"] == 1
    assert "already enqueued" in eda_caplog.text


def test_unique_enqueue_old_job_completed(default_queue, eda_caplog):
    old_job = default_queue.enqueue(fake_task, job_id="fake_task", number=1)
    old_job.set_status("finished")
    job = unique_enqueue(default_queue.name, "fake_task", fake_task, number=2)
    assert job.kwargs["number"] == 2
    assert "Enqueing unique job" in eda_caplog.text


def test_unique_enqueue_old_job_failed(default_queue, eda_caplog):
    old_job = default_queue.enqueue(fake_task, job_id="fake_task", number=1)
    old_job.set_status("failed")
    job = unique_enqueue(default_queue.name, "fake_task", fake_task, number=2)
    assert job.kwargs["number"] == 2
    assert "Enqueing unique job" in eda_caplog.text


def test_unique_enqueue_new_job(default_queue, eda_caplog):
    job = unique_enqueue(default_queue.name, "fake_task", fake_task, number=2)
    assert job.kwargs["number"] == 2
    assert "Enqueing unique job" in eda_caplog.text
