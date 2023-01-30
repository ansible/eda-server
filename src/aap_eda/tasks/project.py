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

from aap_eda.core.tasking import job
from aap_eda.services import project as project_svc

logger = logging.getLogger(__name__)


@job
def import_project(name: str, url: str, description: str = ""):
    logger.info(
        "[Task]: Import project ( name=%s url=%s description=%s )",
        name,
        url,
        description,
    )
    project = project_svc.import_project(
        name=name, url=url, description=description
    )
    logger.info("[Task]: Project imported ( id=%s )", project.id)
    return {"project_id": project.id}


@job
def sync_project(project_id: int):
    logger.info("[Task]: Project sync started (id=%s)", project_id)
    project_svc.sync_project(project_id=project_id)
    logger.info("[Task]: Project sync complete (id=%s)", project_id)
