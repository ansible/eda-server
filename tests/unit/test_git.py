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
import os
import re
import shutil
import subprocess
import typing as tp
from unittest import mock

import pytest
from aap_eda.core.models import Credential
from aap_eda.services.project.git import (
    GitAuthenticationError,
    GitError,
    GitExecutor,
    GitRepository,
)


@pytest.fixture(scope="function")
def update_environment() -> tp.Generator[tp.Callable, None, None]:
    """Fixture factory to update environment variables
    Returns the updated environment variables,
    and restores the original environment variables after the test
    """
    env_backup = os.environ.copy()

    def _update_environment(env: tp.Optional[dict] = None) -> os._Environ:
        if env:
            os.environ.update(env)
        return os.environ

    yield _update_environment
    os.environ.clear()
    os.environ.update(env_backup)


@pytest.fixture
def credential() -> Credential:
    credential = Credential.objects.create(
        name="name", username="me", secret="supersecret"
    )
    credential.refresh_from_db()
    return credential


@pytest.mark.django_db
def test_git_clone(credential: Credential):
    executor = mock.MagicMock(ENVIRON={})
    repository = GitRepository.clone(
        "https://git.example.com/repo.git",
        "/path/to/repository",
        credential=credential,
        _executor=executor,
    )
    executor.assert_called_once_with(
        [
            "clone",
            "--quiet",
            "https://me:supersecret@git.example.com/repo.git",
            "/path/to/repository",
        ],
    )
    assert "GIT_SSL_NO_VERIFY" not in executor.ENVIRON
    assert isinstance(repository, GitRepository)
    assert repository.root == "/path/to/repository"


@mock.patch("subprocess.run")
@pytest.mark.django_db
def test_git_clone_leak_password(
    subprocess_run_mock: mock.Mock,
    credential: Credential,
):
    executor = GitExecutor()

    def raise_error(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            128,
            cmd,
            stderr="fatal: Unable to access "
            "'https://me:supersecret@git.example.com/repo.git'",
        )

    subprocess_run_mock.side_effect = raise_error

    with pytest.raises(GitError) as exc_info:
        GitRepository.clone(
            "https://git.example.com/repo.git",
            "/path/to/repository",
            credential=credential,
            _executor=executor,
        )
    assert "supersecret" not in str(exc_info)
    assert "****" in str(exc_info)


@mock.patch("subprocess.run")
@pytest.mark.django_db
def test_git_clone_auth_error(
    subprocess_run_mock: mock.Mock,
    credential: Credential,
):
    executor = GitExecutor()

    def raise_error(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            128,
            cmd,
            stderr="Authentication failed",
        )

    subprocess_run_mock.side_effect = raise_error

    with pytest.raises(GitAuthenticationError) as exc_info:
        GitRepository.clone(
            "https://git.example.com/repo.git",
            "/path/to/repository",
            credential=credential,
            _executor=executor,
        )
    assert "supersecret" not in str(exc_info)


def test_git_clone_without_ssl_verification():
    executor = mock.MagicMock(ENVIRON={})
    _ = GitRepository.clone(
        "https://git.example.com/repo.git",
        "/path/to/repository",
        verify_ssl=False,
        _executor=executor,
    )
    executor.assert_called_once_with(
        [
            "clone",
            "--quiet",
            "https://git.example.com/repo.git",
            "/path/to/repository",
        ]
    )
    assert executor.ENVIRON["GIT_SSL_NO_VERIFY"] == "true"


def test_git_shallow_clone():
    executor = mock.Mock()
    repository = GitRepository.clone(
        "https://git.example.com/repo.git",
        "/path/to/repository",
        depth=42,
        _executor=executor,
    )

    assert isinstance(repository, GitRepository)
    assert repository.root == "/path/to/repository"
    executor.assert_called_once_with(
        [
            "clone",
            "--quiet",
            "--depth",
            "42",
            "https://git.example.com/repo.git",
            "/path/to/repository",
        ]
    )


def test_git_rev_parse_head():
    executor = mock.Mock()
    executor.return_value.stdout = "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc\n"

    repository = GitRepository("/path/to/repository", _executor=executor)
    result = repository.rev_parse("HEAD")

    assert result == "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc"
    executor.assert_called_once_with(
        ["rev-parse", "HEAD"], cwd="/path/to/repository"
    )


@mock.patch("subprocess.run")
def test_git_executor_call(run_mock: mock.Mock):
    executor = GitExecutor()
    executor(["clone", "https://git.example.com/repo.git", "/test/repo"])
    run_mock.assert_called_once_with(
        [
            shutil.which("git"),
            "clone",
            "https://git.example.com/repo.git",
            "/test/repo",
        ],
        check=True,
        encoding="utf-8",
        env={
            "GIT_TERMINAL_PROMPT": "0",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        cwd=None,
    )


@mock.patch("subprocess.run")
def test_git_executor_timeout(run_mock: mock.Mock):
    timeout = 10

    def raise_timeout(cmd, **_kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=timeout)

    run_mock.side_effect = raise_timeout

    executor = GitExecutor()
    message = re.escape(
        f"""Command '['{shutil.which("git")}', 'status']' """
        """timed out after 10 seconds"""
    )
    with pytest.raises(GitError, match=message):
        executor(["status"], timeout=timeout)


@mock.patch("subprocess.run")
def test_git_executor_error(run_mock: mock.Mock):
    def raise_error(cmd, **_kwargs):
        raise subprocess.CalledProcessError(
            128,
            cmd,
            stderr="fatal: not a git repository",
        )

    run_mock.side_effect = raise_error

    executor = GitExecutor()
    message = re.escape(
        "Command git failed with return code 128. "
        "Error: fatal: not a git repository",
    )
    with pytest.raises(GitError, match=message):
        executor(["status"])


@pytest.mark.parametrize(
    "envvar",
    [
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
    ],
)
def test_set_http_proxy(update_environment, envvar: str):
    test_proxy = "http://example.com:8080"
    update_environment({envvar: test_proxy})

    executor = GitExecutor()
    with mock.patch("subprocess.run"):
        executor(["clone", "https://git.example.com/repo.git", "/test/repo"])

    assert executor.ENVIRON["http_proxy"] == test_proxy
