#  Copyright 2026 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0

from unittest import mock

import pytest
from dispatcherd.worker.exceptions import DispatcherCancel
from django.core.management.base import CommandError
from django.test import override_settings

from aap_eda.core import models
from aap_eda.tasks.management import (
    LOG_PURGE_TASK_TIMEOUT_SECONDS,
    _aap_eda_manage,
    submit_log_purge,
)


@pytest.mark.django_db
def test_submit_log_purge_uses_default_queue_uuid_and_purge_timeout():
    job_id = "712beb16-b7dd-40c9-aa29-a7f734376c7a"
    with mock.patch(
        "aap_eda.tasks.management.uuid4", return_value=job_id
    ), mock.patch(
        "aap_eda.tasks.management.submit_task",
        return_value=({"uuid": job_id}, "default"),
    ) as submit_task:
        assert (
            submit_log_purge(
                retention_duration="P1M",
                audit_trail=True,
                activation_ids=[9],
            )
            == job_id
        )

    (task,) = submit_task.call_args.args
    assert task is _aap_eda_manage
    assert submit_task.call_args.kwargs == {
        "args": (
            job_id,
            "purge_log_records",
            {
                "retention_duration": "P1M",
                "audit_trail": True,
                "activation-ids": [9],
            },
        ),
        "queue": "default",
        "timeout": LOG_PURGE_TASK_TIMEOUT_SECONDS,
        "uuid": job_id,
    }


@pytest.mark.django_db
def test_worker_invokes_purge_command_and_returns_deleted_count(
    default_activation_instances,
):
    logs = [
        models.RulebookProcessLog.objects.create(
            log=f"worker-log-{index}",
            activation_instance=instance,
            log_timestamp=1,
        )
        for index, instance in enumerate(default_activation_instances)
    ]
    job_id = "worker-job-17"

    with mock.patch("aap_eda.tasks.management.logger.info") as log_info:
        result = _aap_eda_manage(
            job_id,
            "purge_log_records",
            {
                "date": "1970-01-02",
                "audit_trail": True,
                "activation-ids": [
                    default_activation_instances[0].activation_id
                ],
            },
        )

    assert result == {
        "job_id": job_id,
        "command": "purge_log_records",
        "status": "completed",
        "deleted": 2,
    }
    assert not models.RulebookProcessLog.objects.filter(
        pk__in=[log.pk for log in logs]
    ).exists()
    assert (
        models.RulebookProcessLog.objects.filter(
            log__contains="were purged at"
        ).count()
        == 2
    )
    assert any(
        call.args[0].startswith("Log purge finished")
        and call.args[1:] == (job_id, "completed", 2)
        for call in log_info.call_args_list
    )


@pytest.mark.django_db
def test_worker_empty_options_obey_zero_retention_setting(
    default_activation_instance,
):
    models.RulebookProcessLog.objects.create(
        log="retained",
        activation_instance=default_activation_instance,
        log_timestamp=1,
    )
    with override_settings(ACTIVATION_DB_LOG_RETENTION_DAYS=0), mock.patch(
        "aap_eda.tasks.management.logger.info"
    ) as log_info:
        result = _aap_eda_manage("no-op-job", "purge_log_records", {})

    assert result == {
        "job_id": "no-op-job",
        "command": "purge_log_records",
        "status": "no-op",
        "deleted": 0,
    }
    assert models.RulebookProcessLog.objects.filter(log="retained").exists()
    assert any(
        call.args[0].startswith("Log purge finished")
        and call.args[1:] == ("no-op-job", "no-op", 0)
        for call in log_info.call_args_list
    )


@pytest.mark.django_db
def test_worker_lock_contention_is_an_observable_skip():
    class NotAcquired:
        def __enter__(self):
            return False

        def __exit__(self, exc_type, exc, traceback):
            return False

    with mock.patch(
        "aap_eda.tasks.management.advisory_lock", return_value=NotAcquired()
    ), mock.patch(
        "aap_eda.tasks.management.call_command"
    ) as call_command, mock.patch(
        "aap_eda.tasks.management.logger.warning"
    ) as log_warning:
        result = _aap_eda_manage("locked-job", "purge_log_records", {})

    assert result["status"] == "skipped"
    assert "advisory lock" in result["reason"]
    call_command.assert_not_called()
    log_warning.assert_called_once()
    assert log_warning.call_args.args[1:] == (
        "locked-job",
        "purge_log_records",
        "another task holds the advisory lock for purge_log_records",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure", [CommandError("partial failure"), DispatcherCancel()]
)
def test_worker_propagates_command_and_timeout_failures(failure):
    with mock.patch(
        "aap_eda.tasks.management.call_command", side_effect=failure
    ), mock.patch(
        "aap_eda.tasks.management.logger.exception"
    ) as log_exception, pytest.raises(
        type(failure)
    ):
        _aap_eda_manage("failed-job", "purge_log_records", {})

    log_exception.assert_called_once()
    assert log_exception.call_args.args[0].startswith(
        "Management command failed"
    )
    assert log_exception.call_args.args[1] == "failed-job"


@pytest.mark.django_db
def test_worker_keeps_generic_management_command_scope():
    with mock.patch(
        "aap_eda.tasks.management.call_command", return_value="finished"
    ) as call_command:
        result = _aap_eda_manage("generic-job", "check", {"deploy": True})

    assert result == {
        "job_id": "generic-job",
        "command": "check",
        "status": "completed",
    }
    call_command.assert_called_once_with("check", no_color=True, deploy=True)
