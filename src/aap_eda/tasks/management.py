#  Copyright 2024 Red Hat, Inc.
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

from ansible_base.lib.utils.db import advisory_lock
from dispatcherd.publish import submit_task
from django.conf import settings
from django.core.management import call_command

from aap_eda import utils

logger = logging.getLogger(__name__)
MANAGEMENT_TASKS_QUEUE = "default"


def aap_eda_manage_commands(command: str, **args) -> str:
    """Execute management command async task using dispatcherd.

    Args:
        command: The name of the Django management command to execute
        **args: Keyword arguments to pass to the management command

    Returns:
        UUID of the submitted task
    """
    queue_name = utils.sanitize_postgres_identifier(MANAGEMENT_TASKS_QUEUE)
    job_data, _ = submit_task(
        _aap_eda_manage,
        queue=queue_name,
        args=(command, args),
        timeout=settings.DISPATCHERD_PROJECT_TASK_TIMEOUT,
    )
    return job_data["uuid"]


def _aap_eda_manage(command: str, args: dict):
    """Wrap _aap_eda_manage_no_lock with advisory lock.

    Args:
        command: The name of the Django management command to execute
        args: Dictionary of keyword arguments to pass to the management command
    """
    with advisory_lock(command, wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already running command {command}, exiting"
            )
            return
        _aap_eda_manage_no_lock(command, args)


def _aap_eda_manage_no_lock(command: str, args: dict):
    """Execute Django management command without lock.

    This function is intended to be run by the tasking system inside the lock.

    Args:
        command: The name of the Django management command to execute
        args: Dictionary of keyword arguments to pass to the management command
    """
    logger.info(
        f"Executing management command '{command}' with parameters: {args}"
    )
    call_command(command, **args)
