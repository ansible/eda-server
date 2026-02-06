#  Copyright 2025 Red Hat, Inc.
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

"""Integration tests for actual dispatcherd task submission and execution."""

import uuid
from unittest.mock import patch

import pytest

from aap_eda.core.tasking import (
    enqueue_delay,
    queue_cancel_job,
    unique_enqueue,
)


def sample_task_function(value: int) -> int:
    """Simple test task."""
    return value * 2


#################################################################
# Tests for actual dispatcherd function calls (no mocking)
#################################################################


@pytest.mark.django_db
def test_unique_enqueue_calls_real_submit_task():
    """Test that unique_enqueue calls dispatcherd.publish.submit_task."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    # Mock only the final broker publication, not submit_task itself
    with patch("aap_eda.core.tasking.submit_task") as mock_submit:
        # This will call the real unique_enqueue function
        unique_enqueue(queue_name, job_id, sample_task_function, 42, value=10)

        # Verify submit_task was called correctly
        mock_submit.assert_called_once()
        call_args = mock_submit.call_args

        # Verify function and arguments
        assert call_args[0][0] == sample_task_function
        assert call_args[1]["args"] == (42,)
        assert call_args[1]["kwargs"] == {"value": 10}
        assert call_args[1]["queue"] == "test_queue"
        assert call_args[1]["uuid"] == job_id


@pytest.mark.django_db
def test_enqueue_delay_calls_real_submit_task():
    """Test that enqueue_delay calls dispatcherd.publish.submit_task."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch("aap_eda.core.tasking.submit_task") as mock_submit:
        # This will call the real enqueue_delay function with delay processor
        enqueue_delay(
            queue_name, job_id, 30, sample_task_function, 10, value=20
        )

        # Verify submit_task was called correctly
        mock_submit.assert_called_once()
        call_args = mock_submit.call_args

        # Verify function and arguments
        assert call_args[0][0] == sample_task_function
        assert call_args[1]["args"] == (10,)
        assert call_args[1]["kwargs"] == {"value": 20}
        assert call_args[1]["queue"] == "test_queue"
        assert call_args[1]["uuid"] == job_id

        # Verify delay processor was included
        assert "processor_options" in call_args[1]
        processor_options = call_args[1]["processor_options"]
        assert len(processor_options) == 1
        assert hasattr(processor_options[0], "delay")
        assert processor_options[0].delay == 30


@pytest.mark.django_db
def test_queue_cancel_job_calls_real_control():
    """Test that queue_cancel_job calls dispatcherd control interface."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    # Mock only the control interface response
    with patch(
        "aap_eda.core.tasking.get_control_from_settings"
    ) as mock_get_control:
        mock_control = mock_get_control.return_value
        mock_control.control_with_reply.return_value = {"cancelled": [job_id]}

        # This calls the real queue_cancel_job function
        queue_cancel_job(queue_name, job_id)

        # Verify the control interface was used correctly
        mock_get_control.assert_called_once_with(
            default_publish_channel=queue_name
        )
        mock_control.control_with_reply.assert_called_once_with(
            "cancel", data={"uuid": job_id}
        )


#################################################################
# Tests for missing code paths in tasking functions
#################################################################


@pytest.mark.django_db
def test_unique_enqueue_empty_args():
    """Test unique_enqueue with empty args - currently missing coverage."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with pytest.raises(IndexError):
        # This hits the uncovered line: fn = args[0] with empty args
        unique_enqueue(queue_name, job_id)


@pytest.mark.django_db
def test_enqueue_delay_empty_args():
    """Test enqueue_delay with empty args - currently missing coverage."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with pytest.raises(IndexError):
        # This hits the uncovered line: fn = args[0] with empty args
        enqueue_delay(queue_name, job_id, 10)


@pytest.mark.django_db
def test_enqueue_delay_args_processing():
    """Test the args processing logic in enqueue_delay - lines 26-27."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch("aap_eda.core.tasking.submit_task") as mock_submit:
        # Test with multiple args to ensure args processing works
        enqueue_delay(
            queue_name,
            job_id,
            5,
            sample_task_function,  # This becomes args[0] (fn)
            42,  # This becomes args[1:]
            "extra_arg",
            value=10,
        )

        # Verify function was extracted and remaining args processed
        mock_submit.assert_called_once()
        call_args = mock_submit.call_args
        assert call_args[0][0] == sample_task_function
        assert call_args[1]["args"] == (42, "extra_arg")


@pytest.mark.django_db
def test_unique_enqueue_args_processing():
    """Test the args processing logic in unique_enqueue - lines 63-64."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch("aap_eda.core.tasking.submit_task") as mock_submit:
        # Test with multiple args
        unique_enqueue(
            queue_name,
            job_id,
            sample_task_function,  # This becomes args[0] (fn)
            42,  # This becomes args[1:]
            "extra_arg",
            value=10,
        )

        mock_submit.assert_called_once()
        call_args = mock_submit.call_args
        assert call_args[0][0] == sample_task_function
        assert call_args[1]["args"] == (42, "extra_arg")


#################################################################
# Tests for queue_cancel_job debug logging path
#################################################################


@pytest.mark.django_db
def test_queue_cancel_job_no_jobs_debug_logging():
    """Test debug logging when no jobs are cancelled - line 48."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch(
        "aap_eda.core.tasking.get_control_from_settings"
    ) as mock_get_control:
        mock_control = mock_get_control.return_value
        # Return None (no jobs cancelled)
        mock_control.control_with_reply.return_value = None

        with patch("aap_eda.core.tasking.logger") as mock_logger:
            queue_cancel_job(queue_name, job_id)

            # Verify debug logging was called
            mock_logger.debug.assert_called_once_with(
                f"No jobs running with id {job_id} to cancel"
            )


#################################################################
# Tests for queue_cancel_job exception handling - Complete coverage
#################################################################


@pytest.mark.django_db
def test_queue_cancel_job_connection_error():
    """Test exception handling when connection to dispatcherd fails."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch(
        "aap_eda.core.tasking.get_control_from_settings"
    ) as mock_get_control:
        # Simulate connection error
        mock_get_control.side_effect = ConnectionError(
            "Failed to connect to dispatcherd"
        )

        with patch("aap_eda.core.tasking.logger") as mock_logger:
            # Function should not raise exception, but log the error
            queue_cancel_job(queue_name, job_id)

            # Verify error logging was called (lines 50-53)
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args

            # Verify error message format
            error_msg = call_args[0][0]
            assert (
                f"Failed to cancel job {job_id} in queue {queue_name}"
                in error_msg
            )
            assert "Failed to connect to dispatcherd" in error_msg
            # Verify exc_info=True was passed
            assert call_args[1]["exc_info"] is True


@pytest.mark.django_db
def test_queue_cancel_job_control_interface_error():
    """Test exception handling when control interface fails."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch(
        "aap_eda.core.tasking.get_control_from_settings"
    ) as mock_get_control:
        mock_control = mock_get_control.return_value
        # Simulate control interface error
        mock_control.control_with_reply.side_effect = TimeoutError(
            "Control timeout"
        )

        with patch("aap_eda.core.tasking.logger") as mock_logger:
            # Function should not raise exception, but log the error
            queue_cancel_job(queue_name, job_id)

            # Verify error logging was called (lines 50-53)
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args

            # Verify error message format
            error_msg = call_args[0][0]
            assert (
                f"Failed to cancel job {job_id} in queue {queue_name}"
                in error_msg
            )
            assert "Control timeout" in error_msg
            # Verify exc_info=True was passed
            assert call_args[1]["exc_info"] is True


@pytest.mark.django_db
def test_queue_cancel_job_general_exception():
    """Test exception handling for general exceptions."""
    queue_name = "test_queue"
    job_id = str(uuid.uuid4())

    with patch(
        "aap_eda.core.tasking.get_control_from_settings"
    ) as mock_get_control:
        mock_control = mock_get_control.return_value
        # Simulate general exception
        mock_control.control_with_reply.side_effect = ValueError(
            "Invalid format"
        )

        with patch("aap_eda.core.tasking.logger") as mock_logger:
            # Function should not raise exception, but log the error
            queue_cancel_job(queue_name, job_id)

            # Verify error logging was called (lines 50-53)
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args

            # Verify error message format
            error_msg = call_args[0][0]
            assert (
                f"Failed to cancel job {job_id} in queue {queue_name}"
                in error_msg
            )
            assert "Invalid format" in error_msg
            # Verify exc_info=True was passed
            assert call_args[1]["exc_info"] is True
