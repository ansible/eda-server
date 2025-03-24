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

from django.conf import settings

from aap_eda.core import models
from aap_eda.services.project import ProjectImportError, ProjectImportService
from ansible_base.lib.utils.db import advisory_lock
from dispatcherd.factories import get_control_from_settings
from dispatcherd.publish import task

logger = logging.getLogger(__name__)
PROJECT_TASKS_QUEUE = "eda_workers"


@task(queue=PROJECT_TASKS_QUEUE)
def import_project(project_id: int):
    with advisory_lock(f"import_project_{project_id}", wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already importing project {project_id}, exiting"
            )
            return

        logger.info(f"Task started: Import project ( {project_id=} )")

        project = models.Project.objects.get(pk=project_id)
        try:
            ProjectImportService().import_project(project)
        except ProjectImportError as e:
            logger.error(e, exc_info=settings.DEBUG)

        logger.info(
            f"Task complete: Import project ( project_id={project.id} )"
        )


@task(queue=PROJECT_TASKS_QUEUE)
def sync_project(project_id: int):
    with advisory_lock(f"import_project_{project_id}", wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already syncing project {project_id}, exiting"
            )
            return

        logger.info(f"Task started: Sync project ( {project_id=} )")

        project = models.Project.objects.get(pk=project_id)
        try:
            ProjectImportService().sync_project(project)
        except ProjectImportError as e:
            logger.error(e, exc_info=settings.DEBUG)

        logger.info(f"Task complete: Sync project ( project_id={project.id} )")


def _monitor_project_tasks_no_lock() -> None:
    """Handle project tasks that are stuck.

    Check if there are projects in PENDING state that doesn't have
    any related job in the queue. If there are any, put them back
    to the queue.
    """
    logger.info("Task started: Monitor project tasks")

    ctl = get_control_from_settings(
        default_publish_channel=PROJECT_TASKS_QUEUE
    )

    # Filter projects that doesn't have any related job
    pending_projects = models.Project.objects.filter(
        import_state=models.Project.ImportState.PENDING
    )
    missing_projects = []
    for project in pending_projects:
        running_data = ctl.control_with_reply(
            "running", data={"uuid": project.import_task_id}
        )
        if not running_data:
            missing_projects.append(project)

    # Sync or import missing projects
    # based on the git_hash field
    for project in missing_projects:
        logger.info(
            "monitor_project_tasks: "
            f"Project {project.name} is missing a job"
            " in the queue. Adding it back."
        )
        if project.git_hash:
            job_data, _ = sync_project.delay(project.id)
        else:
            job_data, _ = import_project.delay(project.id)

        project.import_task_id = job_data["uuid"]
        project.save(update_fields=["import_task_id", "modified_at"])

    logger.info("Task complete: Monitor project tasks")


@task(queue=PROJECT_TASKS_QUEUE)
def _monitor_project_tasks() -> None:
    with advisory_lock("monitor_project_tasks", wait=False) as acquired:
        if not acquired:
            logger.debug(
                "Another task already running monitor_project_tasks, exiting"
            )
            return

        _monitor_project_tasks_no_lock
