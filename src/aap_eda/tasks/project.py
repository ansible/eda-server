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
from aap_eda.core.enums import ActivationStatus, ProcessParentType
from aap_eda.services.project import ProjectImportError, ProjectImportService
from aap_eda.tasks.orchestrator import (
    check_rulebook_queue_health,
    restart_rulebook_process,
    start_rulebook_process,
)

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
    logger.info(f"Task started: Import project ({project_id=})")

    error_message = None
    try:
        project = _get_project_safely(project_id)
        if not project:
            logger.info(
                f"Task complete: Import project "
                f"(project_id={project_id}) - project not found"
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

    logger.info(f"Task complete: Import project (project_id={project_id})")


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

    This function is intended to be run by the tasking system
    inside the lock. After sync completes, handles post-sync
    activation operations (auto-restart and resume waiting).
    """
    logger.info(f"Task started: Sync project ({project_id=})")

    error_message = None
    try:
        project = _get_project_safely(project_id)
        if not project:
            logger.info(
                f"Task complete: Sync project "
                f"(project_id={project_id}) - project not found"
            )
            _handle_sync_failure_activations(
                project_id, "Project not found or deleted"
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

    if error_message:
        _handle_project_error_recovery(project_id, error_message)
        _handle_sync_failure_activations(project_id, error_message)
    else:
        _handle_post_sync_activations(project)

    logger.info(f"Task complete: Sync project (project_id={project_id})")


def _handle_post_sync_activations(project: models.Project):
    """Handle activation operations after a successful sync.

    1. Auto-restart enabled activations with changed content
    2. Resume activations waiting for project sync
    """
    try:
        _auto_restart_activations(project)
    except Exception as e:
        logger.error(
            f"Auto-restart failed for project {project.id}: {e}",
            exc_info=True,
        )

    try:
        _resume_waiting_activations(project)
    except Exception as e:
        logger.error(
            f"Resume waiting activations failed for "
            f"project {project.id}: {e}",
            exc_info=True,
        )


def _auto_restart_activations(project: models.Project):
    """Auto-restart enabled activations when rulebook content changes.

    Excludes activations with awaiting_project_sync=True since
    those will be handled by _resume_waiting_activations.
    Skips activations with source_mappings when content changes,
    as those require manual source mapping updates.
    """
    activations = models.Activation.objects.filter(
        project=project,
        is_enabled=True,
        restart_on_project_update=True,
        awaiting_project_sync=False,
    )

    restart_count = 0
    checked_count = 0
    for activation in activations:
        checked_count += 1
        try:
            current_rulebook = models.Rulebook.objects.get(
                id=activation.rulebook_id
            )
            current_sha256 = current_rulebook.rulesets_sha256
            current_git_hash = project.git_hash

            content_changed = (
                activation.rulebook_rulesets_sha256 != current_sha256
            )
            hash_changed = activation.git_hash != current_git_hash

            if content_changed and activation.source_mappings:
                logger.warning(
                    f"Skipping auto-restart for activation "
                    f"'{activation.name}' - has event stream "
                    f"source mappings that need manual update"
                )
                continue

            # Only auto-restart activations have their cached
            # rulesets updated (filtered by query above).
            if content_changed or hash_changed:
                activation.rulebook_rulesets = current_rulebook.rulesets or ""
                activation.rulebook_rulesets_sha256 = current_sha256
                activation.git_hash = current_git_hash
                activation.save(
                    update_fields=[
                        "rulebook_rulesets",
                        "rulebook_rulesets_sha256",
                        "git_hash",
                    ]
                )

            if content_changed:
                logger.info(
                    f"Content changed for activation "
                    f"'{activation.name}', "
                    f"triggering auto-restart"
                )
                _restart_activation(activation)
                restart_count += 1

        except ObjectDoesNotExist:
            logger.warning(
                f"Rulebook for activation "
                f"'{activation.name}' no longer exists"
            )
        except Exception as e:
            logger.error(
                f"Failed to check activation "
                f"'{activation.name}' for "
                f"auto-restart: {e}",
                exc_info=True,
            )

    logger.info(
        f"Auto-restart check complete: {restart_count} "
        f"activations restarted out of "
        f"{checked_count} checked"
    )


def _restart_activation(activation: models.Activation):
    """Execute auto-restart for an activation."""
    try:
        restart_rulebook_process(
            process_parent_type=ProcessParentType.ACTIVATION,
            process_parent_id=activation.id,
            request_id="",
        )
    except Exception as e:
        logger.error(
            f"Failed to restart activation "
            f"'{activation.name}' after sync: {e}",
            exc_info=True,
        )
        try:
            activation.status = ActivationStatus.ERROR
            activation.status_message = (
                f"Auto-restart failed after project sync: {e}"
            )
            activation.save(update_fields=["status", "status_message"])
        except Exception as save_err:
            logger.error(
                f"Failed to set error state for "
                f"'{activation.name}': {save_err}",
                exc_info=True,
            )
        return

    try:
        activation.restart_count += 1
        activation.save(update_fields=["restart_count"])
    except Exception as e:
        logger.warning(
            f"Restart succeeded for '{activation.name}' "
            f"but failed to update restart_count: {e}",
            exc_info=True,
        )

    logger.info(f"Auto-restarted activation '{activation.name}'")


def _update_activation_content(
    activation: models.Activation,
    project: models.Project,
):
    """Update activation's cached rulebook content, hash, and git hash."""
    try:
        rulebook = models.Rulebook.objects.get(id=activation.rulebook_id)
        activation.rulebook_rulesets = rulebook.rulesets or ""
        activation.rulebook_rulesets_sha256 = rulebook.rulesets_sha256
    except ObjectDoesNotExist:
        logger.warning(
            f"Rulebook for activation "
            f"'{activation.name}' not found, "
            f"keeping existing rulesets"
        )
    activation.git_hash = project.git_hash


def _resume_waiting_activations(project: models.Project):
    """Resume activations waiting for project sync.

    Updates cached rulebook content and git hash before
    starting/restarting to ensure fresh content is used.
    """
    waiting = models.Activation.objects.filter(
        project=project,
        awaiting_project_sync=True,
    )

    for activation in waiting:
        try:
            # Update cached content from post-sync rulebook
            _update_activation_content(activation, project)

            activation.awaiting_project_sync = False
            if not activation.is_enabled:
                logger.info(
                    f"Resuming enable for '{activation.name}' after sync"
                )
                activation.is_enabled = True
                activation.failure_count = 0
                activation.status = ActivationStatus.PENDING
                activation.save(
                    update_fields=[
                        "awaiting_project_sync",
                        "is_enabled",
                        "failure_count",
                        "status",
                        "rulebook_rulesets",
                        "rulebook_rulesets_sha256",
                        "git_hash",
                        "modified_at",
                    ]
                )
                start_rulebook_process(
                    process_parent_type=(ProcessParentType.ACTIVATION),
                    process_parent_id=activation.id,
                    request_id="",
                )
            else:
                logger.info(
                    f"Resuming restart for '{activation.name}' after sync"
                )
                activation.save(
                    update_fields=[
                        "awaiting_project_sync",
                        "rulebook_rulesets",
                        "rulebook_rulesets_sha256",
                        "git_hash",
                    ]
                )
                restart_rulebook_process(
                    process_parent_type=(ProcessParentType.ACTIVATION),
                    process_parent_id=activation.id,
                    request_id="",
                )
        except Exception as e:
            logger.error(
                f"Failed to resume activation "
                f"'{activation.name}' after sync: {e}",
                exc_info=True,
            )
            try:
                activation.status = ActivationStatus.ERROR
                activation.status_message = (
                    f"Failed to start after project sync: {e}"
                )
                activation.awaiting_project_sync = False
                activation.save(
                    update_fields=[
                        "status",
                        "status_message",
                        "awaiting_project_sync",
                    ]
                )
            except Exception as save_err:
                logger.error(
                    f"Failed to update activation status "
                    f"after resume failure: {save_err}",
                    exc_info=True,
                )


def _handle_sync_failure_activations(project_id: int, error_message: str):
    """Handle waiting activations when sync fails."""
    try:
        waiting = models.Activation.objects.filter(
            project_id=project_id,
            awaiting_project_sync=True,
        )
        for activation in waiting:
            try:
                activation.status = ActivationStatus.ERROR
                activation.status_message = (
                    f"Project sync failed: {error_message}"
                )
                activation.awaiting_project_sync = False
                activation.save(
                    update_fields=[
                        "status",
                        "status_message",
                        "awaiting_project_sync",
                    ]
                )
                logger.info(
                    f"Set activation '{activation.name}' "
                    f"to ERROR after sync failure"
                )
            except Exception as e:
                logger.error(
                    f"Failed to update activation "
                    f"'{activation.name}' after "
                    f"sync failure: {e}",
                    exc_info=True,
                )
    except Exception as e:
        logger.error(
            f"Failed to handle sync failure "
            f"activations for project "
            f"{project_id}: {e}",
            exc_info=True,
        )


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

    orphaned = _recover_orphaned_awaiting_activations()
    if orphaned > 0:
        logger.warning(f"Recovered {orphaned} orphaned awaiting activation(s)")

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
            logger.warning(f"Project {project.id} was deleted during recovery")
        except DatabaseError as e:
            logger.error(
                f"Failed to recover project {project.id}: {e}",
                exc_info=True,
            )

    return recovered


def _recover_orphaned_awaiting_activations() -> int:
    """Recover activations stuck with awaiting_project_sync=True.

    Finds activations whose project is no longer syncing
    (COMPLETED, FAILED, or deleted) and either resumes them
    or sets them to ERROR. This is a safety net for races
    where the sync task completes before the flag is set,
    or where sync_project() submission fails silently.
    """
    stuck = models.Activation.objects.filter(
        awaiting_project_sync=True,
    ).select_related("project")

    recovered = 0
    resumed_projects = set()
    for activation in stuck:
        project = activation.project
        # Project deleted or not syncing — activation is orphaned
        if project is None or project.import_state not in [
            models.Project.ImportState.PENDING,
            models.Project.ImportState.RUNNING,
        ]:
            state_desc = "deleted" if project is None else project.import_state
            logger.warning(
                f"Found orphaned activation "
                f"'{activation.name}' with "
                f"awaiting_project_sync=True "
                f"(project state: {state_desc})"
            )
            try:
                if (
                    project is not None
                    and project.import_state
                    == models.Project.ImportState.COMPLETED
                    and project.id not in resumed_projects
                ):
                    # Project synced successfully — resume
                    _resume_waiting_activations(project)
                    resumed_projects.add(project.id)
                else:
                    # Project failed or deleted — set ERROR
                    error_msg = (
                        "Project sync did not complete. "
                        "Recovered by monitoring system."
                    )
                    activation.status = ActivationStatus.ERROR
                    activation.status_message = error_msg
                    activation.awaiting_project_sync = False
                    activation.save(
                        update_fields=[
                            "status",
                            "status_message",
                            "awaiting_project_sync",
                        ]
                    )
                recovered += 1
            except Exception as e:
                logger.error(
                    f"Failed to recover orphaned "
                    f"activation '{activation.name}': {e}",
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
