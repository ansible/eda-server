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


from unittest.mock import patch

import pytest
import redis

from aap_eda.core.tasking import (
    DefaultWorker,
    Queue,
    _create_url_from_parameters,
    get_pending_job,
    get_redis_client,
    logger,
    unique_enqueue,
)
from aap_eda.settings import default


@pytest.fixture
def eda_caplog(caplog_factory):
    return caplog_factory(logger)


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


def test_get_pending_job_existing_job(default_queue):
    job_id = "fake_task"
    job = default_queue.enqueue(fake_task, job_id=job_id, number=1)
    result = get_pending_job(job_id)
    assert result is not None
    assert result.id == job.id


def test_get_pending_job_non_existing_job():
    job_id = "fake_task"
    result = get_pending_job(job_id)
    assert result is None


@patch("aap_eda.settings.default.REDIS_UNIX_SOCKET_PATH", "path/to/socket")
def test_unix_dab_url():
    url = _create_url_from_parameters(
        **default.rq_redis_client_instantiation_parameters()
    )
    assert url == "unix://path/to/socket"


@patch("aap_eda.settings.default.REDIS_UNIX_SOCKET_PATH", None)
@patch("aap_eda.settings.default.REDIS_CLIENT_CERT_PATH", None)
@patch("aap_eda.settings.default.REDIS_HOST", "a-host")
@patch("aap_eda.settings.default.REDIS_PORT", 6379)
def test_redis_dab_url():
    url = _create_url_from_parameters(
        **default.rq_redis_client_instantiation_parameters()
    )
    assert url == "redis://a-host:6379"


@patch("aap_eda.settings.default.REDIS_UNIX_SOCKET_PATH", None)
@patch("aap_eda.settings.default.REDIS_CLIENT_CERT_PATH", "path/to/cert")
@patch("aap_eda.settings.default.REDIS_HOST", "a-different-host")
@patch("aap_eda.settings.default.REDIS_PORT", 6380)
def test_rediss_dab_url():
    url = _create_url_from_parameters(
        **default.rq_redis_client_instantiation_parameters()
    )
    assert url == "rediss://a-different-host:6380"


def test_worker_dab_client(default_queue: Queue):
    """Test that workers end up with a DABRedis client connection."""

    # The default queue has a Redis connection based on the running
    # configuration.  We use that to check the connection type.

    # Verify if given no connection the worker gets the expected type.
    worker = DefaultWorker([default_queue])
    assert isinstance(worker.connection, type(default_queue.connection))

    # Verify if given a redis.Redis connection the worker gets the
    # expected type.
    worker = DefaultWorker(
        [default_queue],
        connection=redis.Redis(
            **default.rq_standalone_redis_client_instantiation_parameters()
        ),
    )
    assert isinstance(worker.connection, type(default_queue.connection))

    # Verify if given a DABRedis/DABRedisCluster connection the worker uses it.
    connection = get_redis_client(
        **default.rq_redis_client_instantiation_parameters()
    )
    worker = DefaultWorker(
        [default_queue],
        connection=connection,
    )
    assert worker.connection is connection

    # Verify if given the queue's DABRedis/DABRedisCluster connection the
    # worker uses it.
    # The queue is created with a DABRedis/DABRedisCluster connection.
    worker = DefaultWorker(
        [default_queue],
        connection=default_queue.connection,
    )
    assert worker.connection is default_queue.connection
