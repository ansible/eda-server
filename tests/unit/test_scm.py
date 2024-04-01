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
from unittest import mock

import pexpect
import pytest

from aap_eda.core.models import EdaCredential
from aap_eda.services.project.scm import (
    PlaybookExecutor,
    ScmError,
    ScmRepository,
)


@pytest.fixture
def credential() -> EdaCredential:
    credential = EdaCredential.objects.create(
        name="test-eda-credential",
        inputs={"username": "adam", "password": "secret"},
    )
    credential.refresh_from_db()
    return credential


@pytest.mark.django_db
def test_git_clone(credential: EdaCredential):
    executor = mock.MagicMock(ENVIRON={})
    repository = ScmRepository.clone(
        "https://git.example.com/repo.git",
        "/path/to/repository",
        credential=credential,
        depth=1,
        branch="branch1",
        refspec="spec1",
        _executor=executor,
    )
    executor.assert_called_once_with(
        [
            "-e",
            (
                "'project_path=/path/to/repository "
                "scm_url=https://adam:secret@git.example.com/repo.git "
                "scm_branch=branch1 scm_refspec=spec1 depth=1'"
            ),
            "-t",
            "update_git",
        ],
    )
    assert "GIT_SSL_NO_VERIFY" not in executor.ENVIRON
    assert isinstance(repository, ScmRepository)
    assert repository.root == "/path/to/repository"


@mock.patch("pexpect.spawn")
@pytest.mark.django_db
def test_git_clone_leak_password(
    pexpect_spawn_mock: mock.Mock,
    credential: EdaCredential,
):
    executor = PlaybookExecutor()

    def raise_error(cmd, **kwargs):
        raise pexpect.exceptions.ExceptionPexpect(
            "fatal: Unable to access "
            "'https://me:supersecret@git.example.com/repo.git'"
        )

    pexpect_spawn_mock.side_effect = raise_error

    with pytest.raises(ScmError) as exc_info:
        ScmRepository.clone(
            "https://git.example.com/repo.git",
            "/path/to/repository",
            credential=credential,
            _executor=executor,
        )
    assert "supersecret" not in str(exc_info)
    assert "****" in str(exc_info)


@mock.patch("pexpect.spawn")
@pytest.mark.django_db
def test_git_clone_timeout(
    pexpect_spawn_mock: mock.Mock,
    credential: EdaCredential,
):
    executor = PlaybookExecutor()

    def raise_error(cmd, **kwargs):
        raise pexpect.exceptions.TIMEOUT("")

    pexpect_spawn_mock.side_effect = raise_error

    with pytest.raises(ScmError) as exc_info:
        ScmRepository.clone(
            "https://git.example.com/repo.git",
            "/path/to/repository",
            credential=credential,
            _executor=executor,
        )
    assert "timeout" in str(exc_info)


def test_git_clone_without_ssl_verification():
    executor = mock.MagicMock(ENVIRON={})
    _ = ScmRepository.clone(
        "https://git.example.com/repo.git",
        "/path/to/repository",
        verify_ssl=False,
        _executor=executor,
    )
    executor.assert_called_once_with(
        [
            "-e",
            (
                "'project_path=/path/to/repository "
                "scm_url=https://git.example.com/repo.git'"
            ),
            "-t",
            "update_git",
        ],
    )
    assert executor.ENVIRON["GIT_SSL_NO_VERIFY"] == "true"


def test_git_rev_parse_head():
    executor = mock.Mock()
    executor.return_value = "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"

    repository = ScmRepository.clone(
        "https://git.example.com/repo.git",
        "/path/to/repository",
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
            ("http://git.example.com/repo.git", "user", "pass", ""),
            "http://user:pass@git.example.com/repo.git",
        ],
        [
            ("http://git.example.com/repo.git", "", "token", ""),
            "http://token@git.example.com/repo.git",
        ],
        [
            ("http://demo:abc@git.example.com/repo.git", "user", "pass", ""),
            "http://user:pass@git.example.com/repo.git",
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
    assert ScmRepository.build_url(*url_params[0]) == url_params[1]
