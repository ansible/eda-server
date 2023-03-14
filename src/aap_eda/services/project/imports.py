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
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Final, Iterator, Optional, Type

import yaml
from django.db import transaction

from aap_eda.core import models
from aap_eda.core.types import StrPath
from aap_eda.services.project.git import GitRepository
from aap_eda.services.rulebook import insert_rulebook_related_data

logger = logging.getLogger(__name__)

TMP_PREFIX: Final = "eda-project-"
YAML_EXTENSIONS = (".yml", ".yaml")


@dataclass
class RulebookInfo:
    relpath: str
    raw_content: str
    content: Any


class ProjectImportError(Exception):
    pass


class ProjectImportService:
    def __init__(self, git_cls: Optional[Type[GitRepository]] = None):
        if git_cls is None:
            git_cls = GitRepository
        self._git_cls = git_cls

    def run(self, project: models.Project):
        project.import_state = models.Project.ImportState.RUNNING
        project.save()
        try:
            with transaction.atomic():
                self._perform_import(project)
                project.import_state = models.Project.ImportState.COMPLETED
                project.save()
        except Exception:
            project.import_state = models.Project.ImportState.FAILED
            project.save()
            raise

    def _perform_import(self, project: models.Project):
        with self._temporary_directory() as tempdir:
            repo_dir = os.path.join(tempdir, "src")

            repo = self._git_cls.clone(project.url, repo_dir, depth=1)
            project.git_hash = repo.rev_parse("HEAD")

            self._import_rulebooks(project, repo_dir)
            self._save_project_archive(project, repo, tempdir)

    def _temporary_directory(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory(prefix=TMP_PREFIX)

    def _import_rulebooks(self, project: models.Project, repo: StrPath):
        for rulebook in self._find_rulebooks(repo):
            self._import_rulebook(project, rulebook)

    def _import_rulebook(
        self, project: models.Project, rulebook_info: RulebookInfo
    ) -> models.Rulebook:
        rulebook = models.Rulebook.objects.create(
            project=project, name=rulebook_info.relpath
        )

        insert_rulebook_related_data(rulebook, rulebook_info.content)
        return rulebook

    def _find_rulebooks(self, repo: StrPath) -> Iterator[RulebookInfo]:
        rulebooks_dir = os.path.join(repo, "rulebooks")
        if not os.path.isdir(rulebooks_dir):
            raise ProjectImportError(
                "The 'rulebooks' directory doesn't exist"
                " within the project root."
            )

        for root, _dirs, files in os.walk(rulebooks_dir):
            for filename in files:
                path = os.path.join(root, filename)
                _base, ext = os.path.splitext(filename)
                if ext not in YAML_EXTENSIONS:
                    continue
                try:
                    info = self._try_load_rulebook(repo, path)
                except Exception:
                    logger.exception(
                        "Unexpected exception when scanning file %s."
                        " Skipping.",
                        path,
                    )
                    continue
                if not info:
                    logger.debug("Not a rulebook file: %s", path)
                    continue
                yield info

    def _try_load_rulebook(
        self, repo_path: StrPath, rulebook_path: StrPath
    ) -> Optional[RulebookInfo]:
        with open(rulebook_path) as f:
            raw_content = f.read()

        try:
            content = yaml.safe_load(raw_content)
        except yaml.YAMLError as exc:
            logger.warning("Invalid YAML file %s: %s", rulebook_path, exc)
            return None

        if not self._is_rulebook_file(content):
            return None

        relpath = os.path.relpath(rulebook_path, repo_path)
        return RulebookInfo(
            relpath=relpath,
            raw_content=raw_content,
            content=content,
        )

    def _is_rulebook_file(self, data: Any) -> bool:
        if not isinstance(data, list):
            return False
        return all("rules" in entry for entry in data)

    def _save_project_archive(
        self,
        project: models.Project,
        repo: GitRepository,
        tempdir: StrPath,
    ):
        archive_file = os.path.join(tempdir, "archive.tar.gz")
        repo.archive("HEAD", archive_file, format="tar.gz")

        filename = f"{project.id:010}.archive.tar.gz"
        with open(archive_file, "rb") as fp:
            project.archive_file.save(filename, fp)
        return project
