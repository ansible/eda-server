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

from ansible_base.lib.utils.db import advisory_lock
from dispatcherd.publish import submit_task
from django.conf import settings

from aap_eda import utils
from aap_eda.core import models
from aap_eda.services.project import ProjectImportError, ProjectImportService

logger = logging.getLogger(__name__)
PROJECT_TASKS_QUEUE = "default"


def import_project(project_id: int) -> str:
    """Import project async task using dispatcherd."""
    queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
    job_data, queue = submit_task(
        _import_project,
        queue=queue_name,
        args=(project_id,),
    )
    return job_data["uuid"]


def _import_project(project_id: int):
    """Wrap _import_project_no_lock with advisory lock."""
    with advisory_lock(f"import_project_{project_id}", wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already importing project {project_id}, exiting"
            )
            return
        _import_project_no_lock(project_id)


def _import_project_no_lock(project_id: int):
    """Import project without lock.

    This function is intended to be run by the tasking system inside the lock.
    """
    logger.info(f"Task started: Import project ( {project_id=} )")

    project = models.Project.objects.get(pk=project_id)
    try:
        ProjectImportService().import_project(project)
    except ProjectImportError as e:
        logger.error(e, exc_info=settings.DEBUG)

    logger.info(f"Task complete: Import project ( project_id={project.id} )")


def sync_project(project_id: int) -> str:
    """Sync project async task using dispatcherd."""
    queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
    job_data, queue = submit_task(
        _sync_project,
        queue=queue_name,
        args=(project_id,),
    )
    return job_data["uuid"]


def _sync_project(project_id: int):
    """Wrap _sync_project_no_lock with advisory lock."""
    with advisory_lock(f"sync_project_{project_id}", wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already syncing project {project_id}, exiting"
            )
            return
        _sync_project_no_lock(project_id)


def _sync_project_no_lock(project_id: int):
    """Sync project without lock.

    This function is intended to be run by the tasking system inside the lock.
    """
    logger.info(f"Task started: Sync project ( {project_id=} )")

    project = models.Project.objects.get(pk=project_id)
    try:
        ProjectImportService().sync_project(project)
    except ProjectImportError as e:
        logger.error(e, exc_info=settings.DEBUG)

    logger.info(f"Task complete: Sync project ( project_id={project.id} )")


# Started by the scheduler, unique concurrent execution
def monitor_project_tasks():
    with advisory_lock("monitor_project_tasks", wait=False) as acquired:
        if not acquired:
            logger.debug(
                "Another task already running monitor_project_tasks, exiting"
            )
            return

        _monitor_project_tasks()


def _monitor_project_tasks() -> None:
    """Handle project tasks that are stuck.

    With dispatcherd, task monitoring is handled internally. This function
    now focuses on cleaning up projects that may be in inconsistent states
    due to external issues.
    """
    logger.info("Task started: Monitor project tasks")

    # Find projects that have been in transition states for a long time
    # Since dispatcherd handles task reliability internally, we only need
    # to handle edge cases where projects might be stuck

    # For now, this is a simplified monitoring approach
    # In a dispatcherd environment, monitoring is handled by the dispatcher
    unfinished_projects = models.Project.objects.filter(
        import_state__in=[
            models.Project.ImportState.PENDING,
            models.Project.ImportState.RUNNING,
        ]
    )

    # Since dispatcherd handles task reliability, we just log the count
    # The actual task recovery is handled by dispatcherd's internal mechanisms
    if unfinished_projects.exists():
        logger.info(
            f"Found {unfinished_projects.count()} projects in transition "
            "states. Dispatcherd handles task recovery."
        )

    logger.info("Task complete: Monitor project tasks")
