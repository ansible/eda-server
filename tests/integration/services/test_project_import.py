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
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.services.project import ProjectImportService
from aap_eda.services.project.git import GitRepository
from aap_eda.services.project.imports import ProjectImportError

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def service_tempdir_mock():
    with (
        tempfile.TemporaryDirectory(prefix="test") as tempdir,
        mock.patch.object(
            ProjectImportService, "_temporary_directory"
        ) as method_mock,
    ):
        tmp_mock = mock.Mock()
        tmp_mock.name = tempdir
        tmp_mock.__enter__ = mock.Mock(return_value=tmp_mock.name)
        tmp_mock.__exit__ = mock.Mock(return_value=None)
        method_mock.return_value = tmp_mock
        yield tmp_mock


@pytest.mark.django_db
@mock.patch("django.core.files.storage.FileSystemStorage.save")
def test_project_import(storage_save_mock, service_tempdir_mock):
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-01"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    def archive_project(_treeish, output, *_args, **_kwargs):
        with open(output, "w") as fp:
            fp.write("REPOSITORY ARCHIVE")

    storage_save_mock.return_value = "project.tar.gz"

    repo_mock = mock.Mock(name="GitRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )

    git_mock = mock.Mock(name="GitRepository", spec=GitRepository)
    git_mock.clone.side_effect = clone_project

    repo_mock.archive.side_effect = archive_project

    project = models.Project.objects.create(
        name="test-project-01", url="https://git.example.com/repo.git"
    )

    service = ProjectImportService(git_cls=git_mock)
    service.run(project)

    git_mock.clone.assert_called_once_with(
        "https://git.example.com/repo.git",
        os.path.join(service_tempdir_mock.name, "src"),
        depth=1,
    )

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.archive_file.name == "project.tar.gz"
    assert project.import_state == models.Project.ImportState.COMPLETED

    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 2

    with open(DATA_DIR / "project-01-import.json") as fp:
        expected_rulebooks = json.load(fp)

    for rulebook, expected in zip(rulebooks, expected_rulebooks):
        assert_rulebook_is_valid(rulebook, expected)

    storage_save_mock.assert_called_once()


@pytest.mark.django_db
@mock.patch("django.core.files.storage.FileSystemStorage.save")
def test_project_import_rulebook_directory_missing(
    storage_save_mock, service_tempdir_mock
):
    storage_save_mock.return_value = "project.tar.gz"
    repo_mock = mock.Mock(name="GitRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    git_mock = mock.Mock(name="GitRepository", spec=GitRepository)
    git_mock.clone.return_value = repo_mock

    project = models.Project.objects.create(
        name="test-project-01", url="https://git.example.com/repo.git"
    )
    message_expected = (
        "The 'rulebooks' directory doesn't exist within the project root."
    )

    service = ProjectImportService(git_cls=git_mock)
    with pytest.raises(
        ProjectImportError,
        match=re.escape(message_expected),
    ):
        service.run(project)

    project = models.Project.objects.get(id=project.id)
    assert project.import_state == models.Project.ImportState.FAILED
    assert project.import_error == message_expected


def assert_rulebook_is_valid(rulebook: models.Rulebook, expected: dict):
    assert rulebook.name == expected["name"]

    rulesets = list(rulebook.ruleset_set.order_by("id"))
    assert len(rulesets) == len(expected["rulesets"])

    for ruleset, expected_rulesets in zip(rulesets, expected["rulesets"]):
        assert_ruleset_is_valid(ruleset, expected_rulesets)


def assert_ruleset_is_valid(ruleset: models.Ruleset, expected: dict):
    assert ruleset.name == expected["name"]

    rules = list(ruleset.rule_set.order_by("id"))
    assert len(rules) == len(expected["rules"])

    for rule, expected_rules in zip(rules, expected["rules"]):
        assert_rule_is_valid(rule, expected_rules)


def assert_rule_is_valid(rule: models.Rule, expected: dict):
    assert rule.name == expected["name"]
    assert rule.action == expected["action"]
