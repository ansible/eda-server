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
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.services.project import ProjectImportService
from aap_eda.services.project.imports import ProjectImportError
from aap_eda.services.project.scm import ScmRepository

# TODO(cutwater): The test cases in this test suite share a lot of common code
#   and it's ugly. It requires refactoring.

DATA_DIR = Path(__file__).parent / "data"


class TestTempdirFactory:
    def __init__(self):
        self.last_name = None

    def __call__(self):
        tempdir = tempfile.TemporaryDirectory(prefix="test")
        self.last_name = tempdir.name
        return tempdir


@pytest.fixture
def service_tempdir_patch():
    factory = TestTempdirFactory()
    with mock.patch.object(
        ProjectImportService, "_temporary_directory", factory
    ):
        yield factory


@pytest.fixture
def storage_save_patch():
    save_mock = mock.Mock()
    with mock.patch(
        "django.core.files.storage.FileSystemStorage.save",
        save_mock,
    ):
        yield save_mock


@pytest.mark.django_db
def test_project_import(storage_save_patch, service_tempdir_patch):
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-01"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    projects = models.Project.objects.bulk_create(
        [
            models.Project(
                name="test-project-01",
                url="https://git.example.com/repo01.git",
                scm_branch="my_branch",
                scm_refspec="the_ref",
            ),
            models.Project(
                name="test-project-02",
                url="https://git.example.com/repo02.git",
                verify_ssl=False,
                scm_branch="tag2",
                scm_refspec="",
            ),
        ]
    )

    for project in projects:
        service = ProjectImportService(scm_cls=git_mock)
        service.import_project(project)
        project.refresh_from_db()

        git_mock.clone.assert_called_with(
            project.url,
            os.path.join(service_tempdir_patch.last_name, "src"),
            credential=None,
            gpg_credential=None,
            depth=1,
            verify_ssl=project.verify_ssl,
            branch=project.scm_branch,
            refspec=project.scm_refspec,
            proxy=project.proxy,
        )

        assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
        assert project.import_state == models.Project.ImportState.COMPLETED

        rulebooks = list(project.rulebook_set.order_by("name"))
        assert len(rulebooks) == 2

        with open(DATA_DIR / "project-01-import.json") as fp:
            expected_rulebooks = json.load(fp)

        for rulebook, expected in zip(rulebooks, expected_rulebooks):
            assert_rulebook_is_valid(rulebook, expected)


@pytest.mark.django_db
def test_project_import_with_new_layout(
    storage_save_patch, service_tempdir_patch
):
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-02"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )

    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    project = models.Project.objects.create(
        name="test-project-01", url="https://git.example.com/repo.git"
    )

    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.import_state == models.Project.ImportState.COMPLETED


@pytest.mark.django_db
def test_project_import_rulebook_directory_missing(
    storage_save_patch, service_tempdir_patch
):
    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.return_value = repo_mock

    project = models.Project.objects.create(
        name="test-project-01", url="https://git.example.com/repo.git"
    )
    message_expected = (
        "The 'extensions/eda/rulebooks' or 'rulebooks'"
        + " directory doesn't exist within the project root."
    )

    service = ProjectImportService(scm_cls=git_mock)
    with pytest.raises(
        ProjectImportError,
        match=re.escape(message_expected),
    ):
        service.import_project(project)

    project = models.Project.objects.get(id=project.id)
    assert project.import_state == models.Project.ImportState.FAILED
    assert project.import_error == message_expected


@pytest.mark.django_db
def test_project_import_with_vaulted_data(
    storage_save_patch, service_tempdir_patch
):
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-04"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )

    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    project = models.Project.objects.create(
        name="test-project-04", url="https://git.example.com/repo.git"
    )

    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.import_state == models.Project.ImportState.COMPLETED


def _setup_project_sync():
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-02"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_hash = "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    repo_mock.rev_parse.return_value = repo_hash
    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    project = models.Project.objects.create(
        name="test-project-01", url="https://git.example.com/repo.git"
    )

    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    assert project.import_state == models.Project.ImportState.COMPLETED

    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 2

    return project


@pytest.mark.django_db
def test_project_sync(storage_save_patch, service_tempdir_patch):
    # TODO(cutwater): Create activations and verify that rulebook content
    #       is updated
    project = _setup_project_sync()
    storage_save_patch.reset_mock()

    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-03"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_hash = "7448d8798a4380162d4b56f9b452e2f6f9e24e7a"
    repo_mock.rev_parse.return_value = repo_hash
    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    service = ProjectImportService(scm_cls=git_mock)
    service.sync_project(project)
    project.refresh_from_db()

    assert project.git_hash == "7448d8798a4380162d4b56f9b452e2f6f9e24e7a"
    assert project.import_state == models.Project.ImportState.COMPLETED

    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 2

    with open(DATA_DIR / "project-03-import.json") as fp:
        expected_rulebooks = json.load(fp)

    for rulebook, expected in zip(rulebooks, expected_rulebooks):
        assert_rulebook_is_valid(rulebook, expected)


@pytest.mark.django_db
def test_project_sync_same_hash(storage_save_patch, service_tempdir_patch):
    project = _setup_project_sync()
    storage_save_patch.reset_mock()

    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-03"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_hash = "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    repo_mock.rev_parse.return_value = repo_hash
    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    service = ProjectImportService(scm_cls=git_mock)
    service.sync_project(project)
    project.refresh_from_db()

    assert project.git_hash == "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    assert project.import_state == models.Project.ImportState.COMPLETED

    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 2

    with open(DATA_DIR / "project-01-import.json") as fp:
        expected_rulebooks = json.load(fp)
    for rulebook, expected in zip(rulebooks, expected_rulebooks):
        assert_rulebook_is_valid(rulebook, expected)
    storage_save_patch.assert_not_called()


@pytest.mark.django_db
def test_project_import_with_invalid_rulebooks(
    storage_save_patch, service_tempdir_patch, caplog
):
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / "project-05"
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )

    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    project = models.Project.objects.create(
        name="test-project-04", url="https://git.example.com/repo.git"
    )

    logger = logging.getLogger("aap_eda")
    propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.WARNING)
    try:
        service = ProjectImportService(scm_cls=git_mock)
        service.import_project(project)
        project.refresh_from_db()
    finally:
        logger.propagate = propagate

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert caplog.text.count("WARNING") == 10

    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 1

    with open(DATA_DIR / "project-05-import.json") as fp:
        expected_rulebooks = json.load(fp)
    for rulebook, expected in zip(rulebooks, expected_rulebooks):
        assert_rulebook_is_valid(rulebook, expected)


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
