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
import os
import tempfile
from unittest import mock

import pytest

from aap_eda.core import models
from aap_eda.core.utils import credentials
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
def ssh_credential(
    default_organization: models.Organization,
) -> models.EdaCredential:
    credential = models.EdaCredential.objects.create(
        name="test-ssh-credential",
        inputs={"ssh_key_data": "-----BEGIN OPENSSH PRIVATE KEY-----\n"},
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
def test_git_clone_sets_proxy_env_during_credential_resolution(
    credential: models.EdaCredential,
):
    """Proxy env vars are set while resolving external credentials."""
    executor = mock.MagicMock()
    captured_env = {}

    original_get = credentials.get_resolved_secrets

    def spy_get(obj):
        captured_env.update(
            {
                k: os.environ.get(k)
                for k in (
                    "http_proxy",
                    "https_proxy",
                    "HTTP_PROXY",
                    "HTTPS_PROXY",
                )
            }
        )
        return original_get(obj)

    with mock.patch(
        "aap_eda.services.project.scm.credentials.get_resolved_secrets",
        side_effect=spy_get,
    ):
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "https://git.example.com/repo.git",
                dest_path,
                credential=credential,
                proxy="http://myproxy:3128",
                _executor=executor,
            )

    assert captured_env["http_proxy"] == "http://myproxy:3128"
    assert captured_env["HTTPS_PROXY"] == "http://myproxy:3128"

    # Env vars should be cleaned up after the with block
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        assert os.environ.get(key) is None


@pytest.mark.django_db
def test_set_proxy_environ_restores_existing_vars(
    credential: models.EdaCredential,
):
    """Pre-existing proxy env vars are restored after clone."""
    executor = mock.MagicMock()
    original_value = "http://original-proxy:8080"

    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ[key] = original_value

    try:
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "https://git.example.com/repo.git",
                dest_path,
                credential=credential,
                proxy="http://override-proxy:3128",
                _executor=executor,
            )

        for key in (
            "http_proxy",
            "https_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
        ):
            assert os.environ.get(key) == original_value
    finally:
        for key in (
            "http_proxy",
            "https_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
        ):
            os.environ.pop(key, None)


@pytest.mark.django_db
def test_git_clone_leak_password(
    credential: models.EdaCredential,
):
    executor = mock.MagicMock()

    def raise_error(**kwargs):
        raise scm.ScmError(
            "fatal: Unable to access "
            "'https://adam:secret@git.example.com/repo.git'"
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
    error_msg = str(exc_info.value)
    assert "secret" not in error_msg
    assert "adam:secret@" not in error_msg
    assert "git.example.com/repo.git" in error_msg


@pytest.mark.django_db
def test_git_clone_no_oracle_attack(
    credential: models.EdaCredential,
):
    """Secret substrings in non-URL parts of the error are not redacted,
    preventing an oracle attack (AAP-72813)."""
    executor = mock.MagicMock()

    def raise_error(**kwargs):
        raise scm.ScmError(
            "Project Import Error: " '"Failed to checkout first-secret-second"'
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
    error_msg = str(exc_info.value)
    assert "first-secret-second" in error_msg


@pytest.mark.django_db
def test_git_clone_sanitizes_decoded_url(
    default_organization: models.Organization,
):
    """URL-decoded credentials are also sanitized (AAP-72813)."""
    credential = models.EdaCredential.objects.create(
        name="special-char-cred",
        inputs={"username": "user", "password": "p@ss"},
        organization=default_organization,
    )
    credential.refresh_from_db()
    executor = mock.MagicMock()

    def raise_error(**kwargs):
        raise scm.ScmError(
            "fatal: Unable to access "
            "'https://user:p@ss@git.example.com/repo.git'"
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
    error_msg = str(exc_info.value)
    assert "p@ss" not in error_msg
    assert "p%40ss" not in error_msg
    assert "git.example.com/repo.git" in error_msg


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
        [
            ("ssh://git@git.example.com/repo.git", "", "", "sshkey"),
            "ssh://git@git.example.com/repo.git",
        ],
        [
            ("ssh://git@git.example.com:2222/repo.git", "", "", "sshkey"),
            "ssh://git@git.example.com:2222/repo.git",
        ],
        [
            ("git+ssh://git@git.example.com/repo.git", "", "", "sshkey"),
            "git+ssh://git@git.example.com/repo.git",
        ],
    ],
)
def test_build_url(url_params):
    assert scm.ScmRepository.build_url(*url_params[0]) == url_params[1]


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


# AAP-65460: SSH clone tests simulating real user project creation
# These verify that when a user creates a project with an SSH URL
# and a Source Control credential containing an SSH key, the
# executor receives the original URL (not corrupted) and a key_file.
@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "git@git.example.com:user/repo.git",
        "ssh://git@git.example.com/ansible/homelab.git",
        "ssh://git@git.example.com:2222/ansible/homelab.git",
        "git+ssh://git@git.example.com/ansible/homelab.git",
    ],
    ids=[
        "git-at-shorthand",
        "ssh-scheme",
        "ssh-scheme-custom-port",
        "git-plus-ssh-scheme",
    ],
)
def test_git_clone_ssh_key(ssh_credential: models.EdaCredential, url: str):
    """Clone with SSH key preserves URL and passes key_file."""
    executor = mock.MagicMock()
    with tempfile.TemporaryDirectory() as dest_path:
        scm.ScmRepository.clone(
            url,
            dest_path,
            credential=ssh_credential,
            depth=1,
            _executor=executor,
        )
        executor.assert_called_once()
        call_kwargs = executor.call_args
        extra_vars = call_kwargs.kwargs["extra_vars"]

        # URL must reach the executor unchanged
        assert extra_vars["scm_url"] == url

        # SSH key file must be provided
        assert "key_file" in extra_vars
        assert extra_vars["key_file"]  # non-empty path


#################################################################
# Tests for GitAnsibleRunnerExecutor._extract_error_msg
#################################################################

_extract = scm.GitAnsibleRunnerExecutor._extract_error_msg


def test_extract_error_msg_standard():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"changed": false, "msg": "Authentication failed"}'
    )
    assert _extract(output) == '"Authentication failed"'


def test_extract_error_msg_multiple_keys():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"changed": false, "rc": 1, '
        '"msg": "Could not clone repo"}'
    )
    assert _extract(output) == '"Could not clone repo"'


def test_extract_error_msg_only_key():
    output = (
        "fatal: [localhost]: FAILED! => " '{"msg": "could not read Username"}'
    )
    assert _extract(output) == '"could not read Username"'


def test_extract_error_msg_brace_in_value():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"changed": false, '
        '"msg": "failed with {error: bad}"}'
    )
    assert _extract(output) == '"failed with {error: bad}"'


def test_extract_error_msg_success_returns_none():
    output = 'ok: [localhost]: SUCCESS => {"changed": true}'
    assert _extract(output) is None


def test_extract_error_msg_no_msg_key_returns_none():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"changed": false, "error": "something"}'
    )
    assert _extract(output) is None


def test_extract_error_msg_empty():
    output = "fatal: [localhost]: FAILED! => " '{"changed": false, "msg": ""}'
    assert _extract(output) == '""'


def test_extract_error_msg_multiline():
    output = (
        "some log output\n"
        "fatal: [localhost]: FAILED! => "
        '{"msg": "real error"}'
    )
    assert _extract(output) == '"real error"'


def test_extract_error_msg_auth_failed():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"msg": "Authentication failed for user@host"}'
    )
    assert _extract(output) == '"Authentication failed for user@host"'


def test_extract_error_msg_username_prompt():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"msg": "could not read Username for '
        "'https://git.example.com'\"}"
    )
    assert _extract(output) == (
        '"could not read Username for ' "'https://git.example.com'\""
    )


def test_extract_error_msg_no_closing_brace():
    output = 'fatal: [localhost]: FAILED! => {"msg": "truncated output'
    assert _extract(output) is None


def test_extract_error_msg_fatal_marker_only():
    output = "fatal: [localhost]: FAILED! => {"
    assert _extract(output) is None


@pytest.mark.django_db
def test_git_clone_gpg_credential(
    default_organization: models.Organization,
):
    """GPG credential sets up verify_commit and GNUPGHOME."""
    gpg_credential = models.EdaCredential.objects.create(
        name="test-gpg-credential",
        inputs={"gpg_public_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"},
        organization=default_organization,
    )
    gpg_credential.refresh_from_db()
    executor = mock.MagicMock()

    with mock.patch.object(scm.ScmRepository, "add_gpg_key"):
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "https://git.example.com/repo.git",
                dest_path,
                gpg_credential=gpg_credential,
                _executor=executor,
            )
            call_kwargs = executor.call_args
            assert call_kwargs[1]["extra_vars"]["verify_commit"] == "true"
            assert "GNUPGHOME" in call_kwargs[1]["env_vars"]


@pytest.mark.django_db
def test_git_clone_creates_directory():
    """Clone creates the destination directory if it doesn't exist."""
    executor = mock.MagicMock()

    with tempfile.TemporaryDirectory() as parent:
        dest_path = os.path.join(parent, "nonexistent")
        scm.ScmRepository.clone(
            "https://git.example.com/repo.git",
            dest_path,
            _executor=executor,
        )
        assert os.path.isdir(dest_path)


@pytest.mark.django_db
def test_git_clone_decrypt_key_file(
    default_organization: models.Organization,
):
    """Clone calls decrypt_key_file when ssh_key_unlock is provided."""
    credential = models.EdaCredential.objects.create(
        name="test-ssh-unlock",
        inputs={
            "ssh_key_data": "-----BEGIN OPENSSH PRIVATE KEY-----\n",
            "ssh_key_unlock": "passphrase",
        },
        organization=default_organization,
    )
    credential.refresh_from_db()
    executor = mock.MagicMock()

    with mock.patch.object(
        scm.ScmRepository, "decrypt_key_file"
    ) as mock_decrypt:
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "git@git.example.com:repo.git",
                dest_path,
                credential=credential,
                _executor=executor,
            )
        mock_decrypt.assert_called_once()


@pytest.mark.django_db
def test_git_clone_gpg_add_key(
    default_organization: models.Organization,
):
    """Clone calls add_gpg_key when gpg_credential is provided."""
    gpg_credential = models.EdaCredential.objects.create(
        name="test-gpg",
        inputs={"gpg_public_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"},
        organization=default_organization,
    )
    gpg_credential.refresh_from_db()
    executor = mock.MagicMock()

    with mock.patch.object(scm.ScmRepository, "add_gpg_key") as mock_add_gpg:
        with tempfile.TemporaryDirectory() as dest_path:
            scm.ScmRepository.clone(
                "https://git.example.com/repo.git",
                dest_path,
                gpg_credential=gpg_credential,
                _executor=executor,
            )
        mock_add_gpg.assert_called_once()


#################################################################
# Tests for ScmRepository.decrypt_key_file and add_gpg_key
#################################################################


def test_decrypt_key_file_success():
    mock_result = mock.Mock()
    mock_result.returncode = 0

    with mock.patch(
        "aap_eda.services.project.scm.subprocess.run",
        return_value=mock_result,
    ) as mock_run:
        scm.ScmRepository.decrypt_key_file("/tmp/keyfile", "passphrase")

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "-P" in args
    assert "passphrase" in args


def test_decrypt_key_file_failure():
    mock_result = mock.Mock()
    mock_result.returncode = 1
    mock_result.stderr = "bad passphrase"
    mock_result.stdout = ""

    with mock.patch(
        "aap_eda.services.project.scm.subprocess.run",
        return_value=mock_result,
    ):
        with pytest.raises(scm.ScmError) as exc_info:
            scm.ScmRepository.decrypt_key_file("/tmp/keyfile", "wrong")
        assert "Failed to decrypt" in str(exc_info.value)


def test_add_gpg_key_success():
    mock_result = mock.Mock()
    mock_result.returncode = 0

    with mock.patch(
        "aap_eda.services.project.scm.subprocess.run",
        return_value=mock_result,
    ) as mock_run:
        scm.ScmRepository.add_gpg_key("/tmp/gpgkey", "/tmp/gnupg")

    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args
    assert call_kwargs[1]["env"] == {"GNUPGHOME": "/tmp/gnupg"}


def test_add_gpg_key_failure():
    mock_result = mock.Mock()
    mock_result.returncode = 2
    mock_result.stderr = "no valid OpenPGP data"
    mock_result.stdout = ""

    with mock.patch(
        "aap_eda.services.project.scm.subprocess.run",
        return_value=mock_result,
    ):
        with pytest.raises(scm.ScmError) as exc_info:
            scm.ScmRepository.add_gpg_key("/tmp/gpgkey", "/tmp/gnupg")
        assert "Failed to import" in str(exc_info.value)


#################################################################
# Tests for GitAnsibleRunnerExecutor.__call__
#################################################################


def _run_executor(runner_rc, runner_stdout):
    """Helper to run GitAnsibleRunnerExecutor with mocked runner."""
    executor = scm.GitAnsibleRunnerExecutor()
    mock_runner = mock.Mock()
    mock_runner.rc = runner_rc

    def fake_run(**kwargs):
        # Write to the captured stdout so redirect_stdout picks it up
        import sys

        sys.stdout.write(runner_stdout)
        return mock_runner

    with mock.patch(
        "aap_eda.services.project.scm.ansible_runner.run",
        side_effect=fake_run,
    ):
        return executor(
            extra_vars={"project_path": "/tmp"},
            env_vars={},
        )


def test_executor_call_success():
    output = '"msg": "Repository Version abc123def456"'
    result = _run_executor(0, output)
    assert result == "abc123def456"


def test_executor_call_success_no_version():
    with pytest.raises(scm.ScmError) as exc_info:
        _run_executor(0, "some output without version")
    assert "Project Import Error:" in str(exc_info.value)


def test_executor_call_auth_failure():
    output = (
        "fatal: [localhost]: FAILED! => "
        '{"changed": false, "msg": "Authentication failed"}'
    )
    with pytest.raises(scm.ScmAuthenticationError):
        _run_executor(1, output)


def test_executor_call_username_prompt():
    output = (
        "fatal: [localhost]: FAILED! => " '{"msg": "could not read Username"}'
    )
    with pytest.raises(scm.ScmAuthenticationError) as exc_info:
        _run_executor(1, output)
    assert "Credentials not provided" in str(exc_info.value)


def test_executor_call_generic_error():
    output = (
        "fatal: [localhost]: FAILED! => " '{"msg": "repository not found"}'
    )
    with pytest.raises(scm.ScmError) as exc_info:
        _run_executor(1, output)
    assert "Project Import Error:" in str(exc_info.value)
    assert "repository not found" in str(exc_info.value)


def test_executor_call_no_fatal_output():
    with pytest.raises(scm.ScmError) as exc_info:
        _run_executor(1, "some generic failure output")
    assert "Project Import Error:" in str(exc_info.value)
