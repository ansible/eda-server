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
from datetime import timedelta
from typing import Optional

from ansible_base.lib.utils.db import advisory_lock
from dispatcherd.publish import submit_task
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, transaction
from django.utils import timezone

from aap_eda import utils
from aap_eda.core import models
from aap_eda.services.project import ProjectImportError, ProjectImportService
from aap_eda.tasks.orchestrator import check_rulebook_queue_health

logger = logging.getLogger(__name__)
PROJECT_TASKS_QUEUE = "default"


def check_project_queue_health() -> bool:
    """Check for the state of the project queue in dispatcherd.

    Returns True if the project queue is healthy, False otherwise.
    """
    try:
        queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
        return check_rulebook_queue_health(queue_name)
    except Exception as e:
        logger.error(f"Project queue health check failed: {e}", exc_info=True)
        return False


def import_project(project_id: int) -> str:
    """Import project async task using dispatcherd."""
    queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
    job_data, queue = submit_task(
        _import_project,
        queue=queue_name,
        args=(project_id,),
        timeout=settings.DISPATCHERD_PROJECT_TASK_TIMEOUT,
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

    error_message = None
    try:
        project = _get_project_safely(project_id)
        if not project:
            logger.info(
                f"Task complete: Import project "
                f"( project_id={project_id} ) - project not found"
            )
            return

        with transaction.atomic():
            ProjectImportService().import_project(project)
            project.last_synced_at = timezone.now()
            project.save(update_fields=["last_synced_at"])
    except ProjectImportError as e:
        logger.error(
            f"Project import error for project {project_id}: {e}",
            exc_info=True,
        )
        error_message = f"Import failed: {str(e)}"
    except DatabaseError as e:
        logger.error(
            f"Database error during project import {project_id}: {e}",
            exc_info=True,
        )
        error_message = "Database error during import"
    except Exception as e:
        logger.error(
            f"Unexpected error during project import {project_id}: {e}",
            exc_info=True,
        )
        error_message = f"Unexpected error during import: {str(e)}"
    finally:
        if error_message:
            _handle_project_error_recovery(project_id, error_message)

    logger.info(f"Task complete: Import project ( project_id={project_id} )")


def sync_project(project_id: int) -> str:
    """Sync project async task using dispatcherd."""
    queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
    job_data, queue = submit_task(
        _sync_project,
        queue=queue_name,
        args=(project_id,),
        timeout=settings.DISPATCHERD_PROJECT_TASK_TIMEOUT,
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

    error_message = None
    try:
        project = _get_project_safely(project_id)
        if not project:
            logger.info(
                f"Task complete: Sync project "
                f"( project_id={project_id} ) - project not found"
            )
            return

        with transaction.atomic():
            ProjectImportService().sync_project(project)
            project.last_synced_at = timezone.now()
            project.save(update_fields=["last_synced_at"])
    except ProjectImportError as e:
        logger.error(
            f"Project sync error for project {project_id}: {e}",
            exc_info=True,
        )
        error_message = f"Sync failed: {str(e)}"
    except DatabaseError as e:
        logger.error(
            f"Database error during project sync {project_id}: {e}",
            exc_info=True,
        )
        error_message = "Database error during sync"
    except Exception as e:
        logger.error(
            f"Unexpected error during project sync {project_id}: {e}",
            exc_info=True,
        )
        error_message = f"Unexpected error during sync: {str(e)}"
    finally:
        if error_message:
            _handle_project_error_recovery(project_id, error_message)

    logger.info(f"Task complete: Sync project ( project_id={project_id} )")


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
    """Handle project tasks that may be stuck in edge cases.

    While dispatcherd handles task reliability internally, this function
    focuses on cleaning up projects that may be in inconsistent states
    due to external issues or crashes that bypass normal error handling.
    """
    logger.info("Task started: Monitor project tasks")

    timeout_threshold = timezone.now() - timedelta(
        seconds=settings.DISPATCHERD_PROJECT_TASK_TIMEOUT * 2
    )

    stuck_count = _recover_stuck_projects(
        models.Project.ImportState.RUNNING,
        timeout_threshold,
        "Task appears to have been abandoned or crashed. "
        "Marked as failed by monitoring system.",
    )
    pending_count = _recover_stuck_projects(
        models.Project.ImportState.PENDING,
        timeout_threshold,
        "Task was stuck in pending state. "
        "Marked as failed by monitoring system.",
    )

    total_stuck = stuck_count + pending_count
    if total_stuck > 0:
        logger.warning(f"Recovered {total_stuck} stuck project(s)")
    else:
        logger.info("No stuck projects found")

    logger.info("Task complete: Monitor project tasks")


def _recover_stuck_projects(
    expected_state: str,
    timeout_threshold,
    error_message: str,
) -> int:
    """Recover projects stuck in the given state past the threshold.

    Uses select_for_update with a double-check pattern to avoid
    race conditions with legitimate in-progress operations.

    Returns the number of projects recovered.
    """
    stuck_projects = models.Project.objects.filter(
        import_state=expected_state,
        modified_at__lt=timeout_threshold,
    )

    recovered = 0
    for project in stuck_projects:
        logger.warning(
            f"Found project {project.id} stuck in "
            f"{expected_state} state since "
            f"{project.modified_at}. Marking as failed."
        )
        try:
            with transaction.atomic():
                fresh = models.Project.objects.select_for_update().get(
                    pk=project.id
                )
                if fresh.import_state == expected_state:
                    fresh.import_state = models.Project.ImportState.FAILED
                    fresh.import_error = error_message
                    fresh.save(
                        update_fields=[
                            "import_state",
                            "import_error",
                        ]
                    )
                    logger.warning(f"Recovered stuck project {project.id}")
                    recovered += 1
        except ObjectDoesNotExist:
            logger.warning(
                f"Project {project.id} was deleted " "during recovery"
            )
        except DatabaseError as e:
            logger.error(
                f"Failed to recover project {project.id}: {e}",
                exc_info=True,
            )

    return recovered


def _get_project_safely(project_id: int) -> Optional[models.Project]:
    """Get project, returning None only if it doesn't exist.

    Returns None if project doesn't exist.
    Raises DatabaseError and other exceptions to be handled by callers,
    which already have appropriate handlers for these cases.
    """
    try:
        return models.Project.objects.get(pk=project_id)
    except ObjectDoesNotExist:
        logger.error(f"Project {project_id} does not exist or was deleted")
        return None


def _handle_project_error_recovery(
    project_id: int, error_message: str
) -> None:
    """Handle error recovery for project operations.

    Attempts to reset project state to FAILED to allow for future
    retry attempts. Uses best-effort approach with transaction safety.

    Args:
        project_id: The project ID (not the object, which may be stale
            after a transaction rollback).
        error_message: Error message to store in import_error.
    """
    try:
        with transaction.atomic():
            fresh_project = models.Project.objects.select_for_update().get(
                pk=project_id
            )
            if fresh_project.import_state in [
                models.Project.ImportState.PENDING,
                models.Project.ImportState.RUNNING,
            ]:
                fresh_project.import_state = models.Project.ImportState.FAILED
                fresh_project.import_error = error_message
                fresh_project.save(
                    update_fields=["import_state", "import_error"]
                )
                logger.info(f"Reset project {project_id} state to FAILED")
    except ObjectDoesNotExist:
        logger.warning(
            f"Project {project_id} was deleted during error recovery"
        )
    except DatabaseError as e:
        logger.critical(
            f"Failed to reset project {project_id} state after "
            f"error (project may be stuck): {e}",
            exc_info=True,
        )
