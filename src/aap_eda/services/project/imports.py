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
from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Final, Iterator, Optional, Type

import yaml
from django.core import exceptions
from django.db import utils

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


def _project_import_wrapper(
    func: Callable[[ProjectImportService, models.Project], None]
):
    @wraps(func)
    def wrapper(self: ProjectImportService, project: models.Project):
        project.import_state = models.Project.ImportState.RUNNING
        project.save()
        try:
            func(self, project)
            project.import_state = models.Project.ImportState.COMPLETED
            project.save()
        except (utils.IntegrityError, exceptions.ObjectDoesNotExist):
            logger.exception("Object may have been deleted")
        except Exception as e:
            try:
                project.import_state = models.Project.ImportState.FAILED
                project.import_error = str(e)
                project.save()
            except exceptions.ObjectDoesNotExist:
                logger.exception("Project may have been deleted")
            raise

    return wrapper


# TODO(cutwater): The project import and project sync are mostly
#   similar operations. Current implementation has some code duplication.
#   This needs to be refactored in the future.
class ProjectImportService:
    def __init__(self, git_cls: Optional[Type[GitRepository]] = None):
        if git_cls is None:
            git_cls = GitRepository
        self._git_cls = git_cls

    @_project_import_wrapper
    def import_project(self, project: models.Project) -> None:
        with self._temporary_directory() as tempdir:
            repo_dir = os.path.join(tempdir, "src")

            repo = self._git_cls.clone(
                project.url,
                repo_dir,
                credential=project.credential,
                depth=1,
                verify_ssl=project.verify_ssl,
            )
            project.git_hash = repo.rev_parse("HEAD")

            self._import_rulebooks(project, repo_dir)

    @_project_import_wrapper
    def sync_project(self, project: models.Project) -> None:
        with self._temporary_directory() as tempdir:
            repo_dir = os.path.join(tempdir, "src")

            repo = self._git_cls.clone(
                project.url,
                repo_dir,
                credential=project.credential,
                depth=1,
                verify_ssl=project.verify_ssl,
            )
            git_hash = repo.rev_parse("HEAD")

            if project.git_hash == git_hash:
                logger.info(
                    "Project (id=%s, name=%s) is up to date. Nothing to sync.",
                    project.id,
                    project.name,
                )
                return

            project.git_hash = git_hash

            self._sync_rulebooks(project, repo_dir, git_hash)

    def _temporary_directory(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory(prefix=TMP_PREFIX)

    def _import_rulebooks(self, project: models.Project, repo: StrPath):
        for rulebook in self._find_rulebooks(repo):
            self._import_rulebook(project, rulebook)

    def _sync_rulebooks(
        self, project: models.Project, repo: StrPath, git_hash: str
    ):
        # TODO(cutwater): The sync must take into account
        #  not rulebook name, but path.
        #  Must be fixed in https://github.com/ansible/aap-eda/pull/139
        existing_rulebooks = {
            obj.name: obj for obj in project.rulebook_set.all()
        }
        for rulebook_info in self._find_rulebooks(repo):
            rulebook = existing_rulebooks.pop(rulebook_info.relpath, None)
            if rulebook is None:
                self._import_rulebook(project, rulebook_info)
            else:
                self._sync_rulebook(rulebook, rulebook_info, git_hash)
        models.Rulebook.objects.filter(
            pk__in=[obj.id for obj in existing_rulebooks.values()]
        ).delete()

    def _import_rulebook(
        self, project: models.Project, rulebook_info: RulebookInfo
    ) -> models.Rulebook:
        rulebook = models.Rulebook.objects.create(
            project=project,
            name=rulebook_info.relpath,
            rulesets=rulebook_info.raw_content,
        )
        insert_rulebook_related_data(rulebook, rulebook_info.content)
        return rulebook

    def _sync_rulebook(
        self,
        rulebook: models.Rulebook,
        rulebook_info: RulebookInfo,
        git_hash: str,
    ):
        if rulebook.rulesets == rulebook_info.raw_content:
            models.Activation.objects.filter(rulebook=rulebook).update(
                git_hash=git_hash,
            )
            return
        rulebook.rulesets = rulebook_info.raw_content
        rulebook.save()
        rulebook.ruleset_set.clear()
        insert_rulebook_related_data(rulebook, rulebook_info.content)
        models.Activation.objects.filter(rulebook=rulebook).update(
            rulebook_rulesets=rulebook.rulesets,
            git_hash=git_hash,
        )

    def _find_rulebooks(self, repo: StrPath) -> Iterator[RulebookInfo]:
        rulebooks_dir = None
        for name in ["extensions/eda/rulebooks", "rulebooks"]:
            if os.path.exists(os.path.join(repo, name)):
                rulebooks_dir = os.path.join(repo, name)
                break

        if not rulebooks_dir:
            raise ProjectImportError(
                "The 'extensions/eda/rulebooks' or 'rulebooks' directory"
                " doesn't exist within the project root."
            )

        for root, _dirs, files in os.walk(rulebooks_dir):
            for filename in files:
                path = os.path.join(root, filename)
                _base, ext = os.path.splitext(filename)
                if ext not in YAML_EXTENSIONS:
                    continue
                try:
                    info = self._try_load_rulebook(rulebooks_dir, path)
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
        self, rulebooks_dir: StrPath, rulebook_path: StrPath
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

        relpath = os.path.relpath(rulebook_path, rulebooks_dir)
        return RulebookInfo(
            relpath=relpath,
            raw_content=raw_content,
            content=content,
        )

    def _is_rulebook_file(self, data: Any) -> bool:
        if not isinstance(data, list):
            return False
        return all("rules" in entry for entry in data)
