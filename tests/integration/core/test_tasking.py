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

from aap_eda.core.tasking import logger, queue_cancel_job, unique_enqueue


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


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.get_control_from_settings")
def test_queue_cancel_job_get_control_failure(mock_get_control, eda_caplog):
    """Test queue_cancel_job when get_control_from_settings fails."""
    # Mock get_control_from_settings to raise an exception
    mock_get_control.side_effect = ConnectionError(
        "Failed to connect to dispatcherd"
    )

    # Function should not raise exception, just log error
    queue_cancel_job("test_queue", "test_job_id")

    # Verify get_control_from_settings was called
    mock_get_control.assert_called_once()

    # Verify error was logged
    assert (
        "Failed to cancel job test_job_id in queue test_queue"
        in eda_caplog.text
    )


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.get_control_from_settings")
def test_queue_cancel_job_control_reply_failure(mock_get_control, eda_caplog):
    """Test queue_cancel_job when control_with_reply fails."""
    # Mock control to raise exception
    mock_control = mock.Mock()
    mock_control.control_with_reply.side_effect = RuntimeError(
        "Dispatcherd error"
    )
    mock_get_control.return_value = mock_control

    # Function should not raise exception, just log error
    queue_cancel_job("test_queue", "test_job_id")

    # Verify calls were made
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        "cancel", data={"uuid": "test_job_id"}
    )

    # Verify error was logged
    assert (
        "Failed to cancel job test_job_id in queue test_queue"
        in eda_caplog.text
    )


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.get_control_from_settings")
def test_queue_cancel_job_timeout(mock_get_control, eda_caplog):
    """Test queue_cancel_job when control_with_reply times out."""
    # Mock control to raise timeout exception
    mock_control = mock.Mock()
    mock_control.control_with_reply.side_effect = TimeoutError(
        "Request timeout"
    )
    mock_get_control.return_value = mock_control

    # Function should not raise exception, just log error
    queue_cancel_job("test_queue", "test_job_id")

    # Verify calls were made
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        "cancel", data={"uuid": "test_job_id"}
    )

    # Verify error was logged
    assert (
        "Failed to cancel job test_job_id in queue test_queue"
        in eda_caplog.text
    )


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.get_control_from_settings")
def test_queue_cancel_job_successful_cancellation(
    mock_get_control, eda_caplog
):
    """Test queue_cancel_job with successful cancellation."""
    # Set warning level logging for this test
    eda_caplog.set_level("WARNING")

    # Mock successful cancellation
    mock_control = mock.Mock()
    mock_control.control_with_reply.return_value = {"cancelled": ["job_id_1"]}
    mock_get_control.return_value = mock_control

    # Function should complete without issues
    queue_cancel_job("test_queue", "test_job_id")

    # Verify calls were made
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        "cancel", data={"uuid": "test_job_id"}
    )

    # Verify warning was logged for canceled jobs
    assert "Canceled jobs in flight" in eda_caplog.text


@pytest.mark.django_db
@mock.patch("aap_eda.core.tasking.get_control_from_settings")
def test_queue_cancel_job_no_jobs_to_cancel(mock_get_control):
    """Test queue_cancel_job when no jobs are running."""
    # Mock no jobs running
    mock_control = mock.Mock()
    mock_control.control_with_reply.return_value = None
    mock_get_control.return_value = mock_control

    # Function should complete without issues and not raise exception
    queue_cancel_job("test_queue", "test_job_id")

    # Verify calls were made
    mock_get_control.assert_called_once()
    mock_control.control_with_reply.assert_called_once_with(
        "cancel", data={"uuid": "test_job_id"}
    )
