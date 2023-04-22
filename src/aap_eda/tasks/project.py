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

from aap_eda.core import models
from aap_eda.core.tasking import job
from aap_eda.services.project import ProjectImportService

logger = logging.getLogger(__name__)


@job
def import_project(project_id: int):
    logger.info(f"Task started: Import project ( {project_id=} )")

    project = models.Project.objects.get(pk=project_id)
    ProjectImportService().import_project(project)

    logger.info(f"Task complete: Import project ( project_id={project.id} )")


@job
def sync_project(project_id: int):
    logger.info(f"Task started: Sync project ( {project_id=} )")

    project = models.Project.objects.get(pk=project_id)
    ProjectImportService().sync_project(project)

    logger.info(f"Task complete: Sync project ( project_id={project.id} )")
