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
import tempfile
from typing import Final

from django.db import transaction

from aap_eda.core import models

from .common import StrPath
from .git import git_current_commit, git_shallow_clone
from .importing import import_files

__all__ = (
    "import_project",
    "sync_project",
)

logger = logging.getLogger(__name__)

TMP_PREFIX: Final = "eda-project"


@transaction.atomic
def import_project(
    *,
    name: str,
    url: str,
    description: str = "",
) -> models.Project:
    with tempfile.TemporaryDirectory(prefix=TMP_PREFIX) as repo_dir:
        commit_id = clone_project(url, repo_dir)
        project = models.Project.objects.create(
            url=url,
            git_hash=commit_id,
            name=name,
            description=description,
        )
        import_files(project, repo_dir)
        # TODO: Save project archive
    return project


def sync_project(project_id: int) -> None:
    raise NotImplementedError


# Utility functions
# ---------------------------------------------------------


def clone_project(url: str, path: StrPath) -> str:
    """Clone repository and return current commit id."""
    git_shallow_clone(url, path)
    return git_current_commit(path)


def save_project_archive(project: models.Project, path: StrPath):
    raise NotImplementedError
