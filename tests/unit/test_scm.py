#  Copyright 2024 Red Hat, Inc.
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
import importlib
import tempfile
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.services.project import scm


@pytest.fixture
def credential(
    default_organization: models.Organization,
) -> models.EdaCredential:
    credential = models.EdaCredential.objects.create(
        name="test-eda-credential",
        inputs={"username": "adam", "password": "secret"},
        organization=default_organization,
    )
    credential.refresh_from_db()
    return credential


@pytest.fixture
def reload_scm():
    yield
    importlib.reload(scm)


@pytest.mark.parametrize(
    "executables,cmd",
    [
        ("git", "git"),
        (["gpg", "gpg2"], "gpg"),
        ("ansible-runner", "ansible-runner"),
        ("ssh-keygen", "ssh-keygen"),
    ],
)
def test_import_module(reload_scm, executables: str | list[str], cmd: str):
    def my_side_effect(*args, **kwargs):
        if args[0] in executables:
            return None
        return "OK"

    with mock.patch(
        "aap_eda.services.project.scm.shutil.which", side_effect=my_side_effect
    ):
        with pytest.raises(Exception) as exc_info:
            importlib.reload(scm)
        assert f"Cannot find {cmd} executable" in str(exc_info.value)


@pytest.mark.django_db
def test_git_clone(credential: models.EdaCredential):
    executor = mock.MagicMock()
    with tempfile.TemporaryDirectory() as dest_path:
        repository = scm.ScmRepository.clone(
            "https://git.example.com/repo.git",
            dest_path,
            credential=credential,
            depth=1,
            branch="branch1",
            refspec="spec1",
            proxy="myproxy.com",
            _executor=executor,
        )
        executor.assert_called_once_with(
            extra_vars={
                "project_path": dest_path,
                "scm_url": "https://adam:secret@git.example.com/repo.git",
                "scm_branch": "branch1",
                "scm_refspec": "spec1",
                "depth": 1,
            },
            env_vars={
                "http_proxy": "myproxy.com",
                "https_proxy": "myproxy.com",
                "HTTP_PROXY": "myproxy.com",
                "HTTPS_PROXY": "myproxy.com",
            },
        )
        assert isinstance(repository, scm.ScmRepository)
        assert repository.root == dest_path


@pytest.mark.django_db
def test_git_clone_leak_password(
    credential: models.EdaCredential,
):
    executor = mock.MagicMock()

    def raise_error(**kwargs):
        raise scm.ScmError(
            "fatal: Unable to access "
            "'https://me:supersecret@git.example.com/repo.git'"
        )

    executor.side_effect = raise_error

    with pytest.raises(scm.ScmError) as exc_info:
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "https://git.example.com/repo.git",
                dest_path,
                credential=credential,
                _executor=executor,
            )
    assert "supersecret" not in str(exc_info)
    assert "****" in str(exc_info)


def test_git_clone_without_ssl_verification():
    executor = mock.MagicMock()
    with tempfile.TemporaryDirectory() as dest_path:
        scm.ScmRepository.clone(
            "https://adam:secret@git.example.com/repo.git",
            dest_path,
            verify_ssl=False,
            _executor=executor,
        )
        executor.assert_called_once_with(
            extra_vars={
                "project_path": dest_path,
                "ssl_no_verify": "true",
                "scm_url": "https://adam:secret@git.example.com/repo.git",
            },
            env_vars={},
        )


@pytest.mark.django_db
def test_git_clone_empty_project(
    credential: models.EdaCredential,
):
    executor = mock.MagicMock()

    def raise_error(**kwargs):
        raise scm.ScmError("Project folder is empty.")

    executor.side_effect = raise_error

    with pytest.raises(scm.ScmError) as exc_info:
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "https://git.example.com/repo.git",
                dest_path,
                credential=credential,
                _executor=executor,
            )
    assert "Project folder is empty." in str(exc_info)


def test_git_rev_parse_head():
    executor = mock.Mock()
    executor.return_value = "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"

    with tempfile.TemporaryDirectory() as dest_path:
        repository = scm.ScmRepository.clone(
            "https://git.example.com/repo.git",
            dest_path,
            _executor=executor,
        )
    result = repository.rev_parse("HEAD")

    assert result == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"


@pytest.mark.parametrize(
    "url_params",
    [
        [
            ("git@git.example.com:user/repo.git", "", "", "sshkey"),
            "git@git.example.com:user/repo.git",
        ],
        [
            ("http://git.example.com/repo.git", "user", "pass@%", ""),
            "http://user:pass%40%25@git.example.com/repo.git",
        ],
        [
            ("http://git.example.com/repo.git", "", "token@A", ""),
            "http://token%40A@git.example.com/repo.git",
        ],
        [
            ("http://demo:abc@git.example.com/repo.git", "user", "pass@B", ""),
            "http://user:pass%40B@git.example.com/repo.git",
        ],
        [
            (
                "git+ssh://demo:abc@git.example.com/repo.git",
                "user",
                "pass",
                "",
            ),
            "git+ssh://user:pass@git.example.com/repo.git",
        ],
        [
            ("git://demo:abc@git.example.com/repo.git", "user", "pass", ""),
            "git://user:pass@git.example.com/repo.git",
        ],
        [
            ("ssh://demo:abc@git.example.com/repo.git", "", "", ""),
            "ssh://git.example.com/repo.git",
        ],
    ],
)
def test_build_url(url_params):
    assert scm.ScmRepository.build_url(*url_params[0]) == url_params[1]


@pytest.mark.parametrize(
    "url,expected",
    [
        ("git@git.ex-ample.com:user/repo.git", True),
        ("http://git.example.com/repo.git/sub/r2.git", True),  # /NOSONAR
        ("https://git.example.com/repo", True),
        ("ssh://git.example.com/repo.git/", True),
        ("git://git.example.com/repo.git", True),
        ("git+ssh://git.example.com/repo.git", True),
        ("git@git.example.com:user/{{lookup}}.git", False),
        ("http://{{lookup}}/repo.git", False),  # /NOSONAR
        ("{{lookup}}//git.example.com/repo.git", False),
        ("ssh://git.example.com/re^po.git", False),
    ],
)
def test_is_git_url_valid(url: str, expected: bool):
    assert scm.is_git_url_valid(url) is expected


@pytest.mark.parametrize(
    "ref,is_branch,expected",
    [
        ("refs/heads/branch1", False, True),
        ("@{-1}", True, False),
        ("branch1", True, True),
        ("{{lookup('branch1')}}", True, True),
        ("{{lookup('branch1')}}", False, False),
    ],
)
def test_is_refspec_valid(ref: str, is_branch: bool, expected: bool):
    assert scm.is_refspec_valid(ref, is_branch) is expected
