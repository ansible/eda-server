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
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.services.project import ProjectImportService
from aap_eda.services.project.scm import ScmRepository

DATA_DIR = Path(__file__).parent / "data"


class TestTempdirFactory:
    __test__ = False

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


@pytest.fixture
def project(default_organization: models.Organization):
    return models.Project.objects.create(
        name="test-project-01",
        url="https://git.example.com/repo.git",
        organization=default_organization,
    )


@pytest.fixture
def projects(default_organization: models.Organization):
    return models.Project.objects.bulk_create(
        [
            models.Project(
                name="test-project-01",
                url="https://git.example.com/repo01.git",
                scm_branch="my_branch",
                scm_refspec="the_ref",
                organization=default_organization,
            ),
            models.Project(
                name="test-project-02",
                url="https://git.example.com/repo02.git",
                verify_ssl=False,
                scm_branch="tag2",
                scm_refspec="",
                organization=default_organization,
            ),
        ]
    )


def _mock_git_clone(source: str, git_hash: str) -> mock.Mock:
    def clone_project(_url, path, *_args, **_kwargs):
        src = DATA_DIR / source
        shutil.copytree(src, path, symlinks=False)
        return repo_mock

    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = git_hash

    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.side_effect = clone_project

    return git_mock


@pytest.mark.django_db
def test_project_import(
    projects: list[models.Project],
    storage_save_patch,
    service_tempdir_patch,
):
    git_mock = _mock_git_clone(
        "project-01", "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
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
            proxy=None,
        )

        assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
        assert project.import_state == models.Project.ImportState.COMPLETED
        assert project.rulebook_set.count() == 2


@pytest.mark.django_db
def test_project_import_with_new_layout(
    project: models.Project,
    storage_save_patch,
    service_tempdir_patch,
):
    git_mock = _mock_git_clone(
        "project-02", "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.import_state == models.Project.ImportState.COMPLETED


@pytest.mark.django_db
def test_project_import_rulebook_directory_missing(
    project: models.Project,
    storage_save_patch,
    service_tempdir_patch,
):
    repo_mock = mock.Mock(name="ScmRepository()")
    repo_mock.rev_parse.return_value = (
        "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    git_mock = mock.Mock(name="ScmRepository", spec=ScmRepository)
    git_mock.clone.return_value = repo_mock

    message_expected = (
        "The 'extensions/eda/rulebooks' or 'rulebooks'"
        + " directory doesn't exist within the project root."
    )

    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)

    project = models.Project.objects.get(id=project.id)
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.import_error == message_expected

    service.sync_project(project)
    project.refresh_from_db()
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.import_error == message_expected


@pytest.mark.django_db
def test_project_import_with_no_rulebooks(
    project: models.Project,
    storage_save_patch,
    service_tempdir_patch,
):
    git_mock = _mock_git_clone(
        "project-06", "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.import_error == "This project contains no rulebooks."
    assert project.rulebook_set.count() == 0


@pytest.mark.django_db
def test_project_import_with_vaulted_data(
    project: models.Project,
    storage_save_patch,
    service_tempdir_patch,
):
    git_mock = _mock_git_clone(
        "project-04", "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    )
    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    assert project.import_state == models.Project.ImportState.COMPLETED


def _setup_project_sync(project: models.Project):
    git_mock = _mock_git_clone(
        "project-02", "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    )
    service = ProjectImportService(scm_cls=git_mock)
    service.import_project(project)
    project.refresh_from_db()

    assert project.git_hash == "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.rulebook_set.count() == 2

    return project


@pytest.mark.django_db
def test_project_sync(
    project: models.Project,
    default_organization: models.Organization,
    storage_save_patch,
    service_tempdir_patch,
):
    # TODO(cutwater): Create activations and verify that rulebook content
    #       is updated
    _setup_project_sync(project)
    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 2
    assert rulebooks[0].name == "hello_events.yml"
    assert rulebooks[1].name == "kafka/kafka-test-rules.yml"
    storage_save_patch.reset_mock()

    git_mock = _mock_git_clone(
        "project-03", "7448d8798a4380162d4b56f9b452e2f6f9e24e7a"
    )
    service = ProjectImportService(scm_cls=git_mock)
    service.sync_project(project)
    project.refresh_from_db()

    assert project.git_hash == "7448d8798a4380162d4b56f9b452e2f6f9e24e7a"
    assert project.import_state == models.Project.ImportState.COMPLETED
    rulebooks = list(project.rulebook_set.order_by("name"))
    assert len(rulebooks) == 2
    assert rulebooks[0].name == "hello_events-new.yml"
    assert rulebooks[1].name == "kafka/kafka-test-rules.yml"


@pytest.mark.django_db
def test_project_sync_same_hash(
    project: models.Project,
    storage_save_patch,
    service_tempdir_patch,
):
    _setup_project_sync(project)
    storage_save_patch.reset_mock()

    git_mock = _mock_git_clone(
        "project-03", "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    )
    service = ProjectImportService(scm_cls=git_mock)
    service.sync_project(project)
    project.refresh_from_db()

    assert project.git_hash == "e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    assert project.import_state == models.Project.ImportState.COMPLETED
    assert project.rulebook_set.count() == 2

    storage_save_patch.assert_not_called()


@pytest.mark.django_db
def test_project_import_with_invalid_rulebooks(
    project: models.Project,
    storage_save_patch,
    service_tempdir_patch,
    caplog,
):
    git_mock = _mock_git_clone(
        "project-05", "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
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
    assert project.rulebook_set.count() == 1
