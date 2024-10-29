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
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Final, Iterator, Optional, Type

import yaml
from django.conf import settings
from django.core import exceptions

from aap_eda.core import models
from aap_eda.core.types import StrPath
from aap_eda.services.project.scm import ScmEmptyError, ScmRepository
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


class MalformedError(Exception):
    pass


def _project_import_wrapper(
    func: Callable[[ProjectImportService, models.Project], None]
):
    @wraps(func)
    def wrapper(self: ProjectImportService, project: models.Project):
        project.import_state = models.Project.ImportState.RUNNING
        project.save(update_fields=["import_state"])
        error = None
        try:
            func(self, project)
            project.import_state = models.Project.ImportState.COMPLETED
        except ScmEmptyError as e:
            # if a project is empty, sync status should show completed
            project.import_state = models.Project.ImportState.COMPLETED
            project.import_error = str(e)
        except Exception as e:
            project.import_state = models.Project.ImportState.FAILED
            project.import_error = str(e)
            error = e
        finally:
            try:
                project.save(
                    update_fields=["import_state", "import_error", "git_hash"]
                )
            except exceptions.ObjectDoesNotExist:
                raise ProjectImportError(
                    "Project may have been deleted"
                ) from error
            else:
                if error and isinstance(error, ProjectImportError):
                    raise error
                elif error:
                    raise ProjectImportError(
                        f"Failed to import the project: {str(error)}"
                    ) from error

    return wrapper


class ProjectImportService:
    def __init__(self, scm_cls: Optional[Type[ScmRepository]] = None):
        if scm_cls is None:
            scm_cls = ScmRepository
        self._scm_cls = scm_cls

    @_project_import_wrapper
    def import_project(self, project: models.Project) -> None:
        with self._clone_and_process(project) as (repo_dir, git_hash):
            project.git_hash = git_hash
            self._import_rulebooks(project, repo_dir)

    @_project_import_wrapper
    def sync_project(self, project: models.Project) -> None:
        with self._clone_and_process(project) as (repo_dir, git_hash):
            # At this point project.import_state and
            # project.import_error have been cleared. We are relying on
            # project.rulebook_set to determine whether previous sync
            # succeeded or not
            if (
                project.git_hash == git_hash
                and project.rulebook_set.count() > 0
            ):
                logger.info(
                    "Project (id=%s, name=%s) is up to date. Nothing to sync.",
                    project.id,
                    project.name,
                )
                return

            project.git_hash = git_hash

            self._sync_rulebooks(project, repo_dir, git_hash)

    @contextmanager
    def _clone_and_process(self, project: models.Project):
        with self._temporary_directory() as tempdir:
            repo_dir = os.path.join(tempdir, "src")

            proxy = project.proxy.get_secret_value() if project.proxy else None
            repo = self._scm_cls.clone(
                project.url,
                repo_dir,
                credential=project.eda_credential,
                gpg_credential=project.signature_validation_credential,
                depth=1,
                verify_ssl=project.verify_ssl,
                branch=project.scm_branch,
                refspec=project.scm_refspec,
                proxy=proxy,
            )
            yield repo_dir, repo.rev_parse("HEAD")
            if project.rulebook_set.count() == 0:
                raise ScmEmptyError("This project contains no rulebooks.")

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
            organization=project.organization,
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
                    logger.error(
                        "Unexpected exception when scanning file %s."
                        " Skipping.",
                        path,
                        exc_info=settings.DEBUG,
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

        try:
            self._validate_rulebook_file(content)
        except MalformedError as exc:
            logger.warning("Malformed rulebook %s: %s", rulebook_path, exc)
            return None

        relpath = os.path.relpath(rulebook_path, rulebooks_dir)
        return RulebookInfo(
            relpath=relpath,
            raw_content=raw_content,
            content=content,
        )

    def _validate_rulebook_file(self, data: Any) -> None:
        if not isinstance(data, list):
            raise MalformedError("rulebook must contain a list of rulesets")
        required_keys = ["name", "condition", "action|actions"]
        for ruleset in data:
            if "rules" not in ruleset:
                raise MalformedError("no rules in a ruleset")
            rules = ruleset["rules"]
            if not isinstance(rules, list):
                raise MalformedError("ruleset must contain a list of rules")
            for rule in rules:
                if not all(
                    any(any_key in rule for any_key in key.split("|"))
                    for key in required_keys
                ):
                    raise MalformedError(
                        f"ruleset must contain {required_keys}"
                    )

                if not all(
                    any(
                        rule.get(any_key) is not None
                        for any_key in key.split("|")
                    )
                    for key in required_keys
                ):
                    raise MalformedError(
                        f"rule's {required_keys} must have non empty values"
                    )
