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
from aap_eda.core.tasking import get_queue, job, unique_enqueue
from aap_eda.services.project import ProjectImportError, ProjectImportService

logger = logging.getLogger(__name__)
PROJECT_TASKS_QUEUE = "default"


@job(PROJECT_TASKS_QUEUE)
def import_project(project_id: int):
    logger.info(f"Task started: Import project ( {project_id=} )")

    project = models.Project.objects.get(pk=project_id)
    try:
        ProjectImportService().import_project(project)
    except ProjectImportError as e:
        logger.error(e, exc_info=settings.DEBUG)

    logger.info(f"Task complete: Import project ( project_id={project.id} )")


@job(PROJECT_TASKS_QUEUE)
def sync_project(project_id: int):
    logger.info(f"Task started: Sync project ( {project_id=} )")

    project = models.Project.objects.get(pk=project_id)
    try:
        ProjectImportService().sync_project(project)
    except ProjectImportError as e:
        logger.error(e, exc_info=settings.DEBUG)

    logger.info(f"Task complete: Sync project ( project_id={project.id} )")


# Started by the scheduler, unique concurrent execution on specified queue;
# default is the default queue
def monitor_project_tasks(queue_name: str = PROJECT_TASKS_QUEUE):
    job_id = "monitor_project_tasks"
    unique_enqueue(queue_name, job_id, _monitor_project_tasks, queue_name)


def _monitor_project_tasks(queue_name: str) -> None:
    """Handle project tasks that are stuck.

    Check if there are projects in PENDING state that doesn't have
    any related job in the queue. If there are any, put them back
    to the queue.
    """
    logger.info("Task started: Monitor project tasks")

    queue = get_queue(queue_name)

    # Filter projects that doesn't have any related job
    pending_projects = models.Project.objects.filter(
        import_state=models.Project.ImportState.PENDING
    )
    missing_projects = []
    for project in pending_projects:
        job = queue.fetch_job(str(project.import_task_id))
        if job is None:
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
            job = sync_project.delay(project.id)
        else:
            job = import_project.delay(project.id)

        project.import_task_id = job.id
        project.save(update_fields=["import_task_id", "modified_at"])

    logger.info("Task complete: Monitor project tasks")
