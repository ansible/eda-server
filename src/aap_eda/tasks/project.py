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
import typing as tp

import django_rq
from ansible_base.lib.utils.db import advisory_lock
from dispatcherd.publish import submit_task
from django.conf import settings

from aap_eda import utils
from aap_eda.core import models, tasking
from aap_eda.services.project import ProjectImportError, ProjectImportService
from aap_eda.settings import features

logger = logging.getLogger(__name__)
PROJECT_TASKS_QUEUE = "default"

# Wrap the django_rq job decorator so its processing is within our retry
# code.


def import_project(project_id: int) -> tp.Optional[str]:
    """Import project async task.

    Proxy for import_project_dispatcherd and import_project_rq.
    """
    with advisory_lock(f"import_project_{project_id}", wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already importing project {project_id}, exiting"
            )
            return None
        if features.DISPATCHERD:
            return import_project_dispatcherd(project_id)

        # rq
        job_data = import_project_rq(project_id)
        return job_data.id


def import_project_dispatcherd(project_id: int) -> str:
    queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
    job_data, queue = submit_task(
        _import_project,
        queue=queue_name,
        args=(project_id,),
    )
    return job_data["uuid"]


@tasking.redis_connect_retry()
def import_project_rq(project_id: int) -> tasking.Job:
    queue = django_rq.get_queue(name=PROJECT_TASKS_QUEUE)
    return queue.enqueue(_import_project, project_id=project_id)


def _import_project(project_id: int):
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


def sync_project(project_id: int) -> tp.Optional[str]:
    """Sync project async task.

    Proxy for sync_project_dispatcherd and sync_project_rq.
    """
    with advisory_lock(f"sync_project_{project_id}", wait=False) as acquired:
        if not acquired:
            logger.debug(
                f"Another task already syncing project {project_id}, exiting"
            )
            return None
        if features.DISPATCHERD:
            return sync_project_dispatcherd(project_id)
        # rq
        job_data = sync_project_rq(project_id)
        return job_data.id


def sync_project_dispatcherd(project_id: int) -> str:
    queue_name = utils.sanitize_postgres_identifier(PROJECT_TASKS_QUEUE)
    job_data, queue = submit_task(
        _sync_project,
        queue=queue_name,
        args=(project_id,),
    )
    return job_data["uuid"]


@tasking.redis_connect_retry()
def sync_project_rq(project_id: int):
    queue = django_rq.get_queue(name=PROJECT_TASKS_QUEUE)
    return queue.enqueue(_sync_project, project_id=project_id)


def _sync_project(project_id: int):
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
    with advisory_lock("monitor_project_tasks", wait=False) as acquired:
        if not acquired:
            logger.debug(
                "Another task already running monitor_project_tasks, exiting"
            )
            return

        _monitor_project_tasks(queue_name)


# Although this is a periodically run task and that could be viewed as
# providing resilience to Redis connection issues we decorate it with the
# redis_connect_retry to maintain the model that anything directly dependent on
# a Redis connection is wrapped by retries.
@tasking.redis_connect_retry()
def _monitor_project_tasks(queue_name: str) -> None:
    """Handle project tasks that are stuck.

    Check if there are projects in PENDING state that doesn't have
    any related job in the queue. If there are any, put them back
    to the queue.
    """
    logger.info("Task started: Monitor project tasks")

    queue = django_rq.get_queue(queue_name)

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
