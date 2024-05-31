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
from __future__ import annotations

import contextlib
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from importlib import resources
from typing import Optional
from urllib.parse import quote, urlparse, urlunparse

import ansible_runner

from aap_eda.core.models import EdaCredential
from aap_eda.core.types import StrPath
from aap_eda.core.utils.credentials import inputs_from_store

logger = logging.getLogger(__name__)


class ScmError(Exception):
    """Ansible-playbook command error."""

    pass


class ScmAuthenticationError(Exception):
    """SCM Authentication error."""

    pass


class ExecutableNotFoundError(Exception):
    """Executable Not Found error."""

    pass


PLAYBOOK = str(
    resources.files("aap_eda.data.playbooks").joinpath("project_clone.yml")
)

KEYGEN_COMMAND = shutil.which("ssh-keygen")
if KEYGEN_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find ssh-keygen executable")

GPG_COMMAND = shutil.which("gpg2")
if GPG_COMMAND is None:
    GPG_COMMAND = shutil.which("gpg")
if GPG_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find gpg executable")

RUNNER_COMMAND = shutil.which("ansible-runner")
if RUNNER_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find ansible-runner executable")


class ScmRepository:
    """Represents a SCM repository."""

    def __init__(
        self,
        root: StrPath,
        *,
        _executor: Optional[GitAnsibleRunnerExecutor] = None,
    ):
        """
        Create an instance for existing repository.

        :param root: Repository root directory.
        :param _executor: Optional command executor.
        """
        self.root = root
        if _executor is None:
            _executor = GitAnsibleRunnerExecutor()
        self._executor = _executor
        self.git_hash = None

    def rev_parse(self, rev: str) -> str:
        """
        Return object identifier for the given revision specifier.

        :param rev: Revision specifier. Currently ignored.
                    Always return identifier of the cloned branch.
        :return: SCM object identifier
        """
        return self.git_hash

    @classmethod
    def clone(
        cls,
        url: str,
        path: StrPath,
        *,
        credential: Optional[EdaCredential] = None,
        gpg_credential: Optional[EdaCredential] = None,
        depth: Optional[int] = None,
        verify_ssl: bool = True,
        branch: Optional[str] = None,
        refspec: Optional[str] = None,
        proxy: Optional[str] = None,
        _executor: Optional[GitAnsibleRunnerExecutor] = None,
    ) -> ScmRepository:
        """
        Clone a repository from url into target path.

        :param url: The repository URL to clone from.
        :param path: The directory to clone into.
        :credential: The credential used to checkout the project
        :gpg_credential: The credential used to verify the commit
        :param depth: If set, creates a shallow clone with a history truncated
            to the specified number of commits.
        :param verify_ssl: Indicates if SSL verification is enabled.
        :param branch: Optional branch/tag/revision
        :param refspec: Optional
        :param _executor: Optional command executor.
        :return:
        """
        if _executor is None:
            _executor = GitAnsibleRunnerExecutor()

        if not os.path.isdir(path):
            os.makedirs(path)
        extra_vars = {"project_path": path}
        env_vars = {}
        final_url = url
        secret = ""
        key_file = None
        key_password = None
        gpg_key_file = None
        gpg_home_dir = None
        if credential:
            inputs = inputs_from_store(credential.inputs.get_secret_value())
            secret = inputs.get("password", "")
            key_data = inputs.get("ssh_key_data", "")

            final_url = cls.build_url(
                url,
                inputs.get("username", ""),
                secret,
                key_data,
            )

            if key_data:  # ssh
                key_file = tempfile.NamedTemporaryFile("w+t")
                key_file.write(key_data)
                key_file.write("\n")
                key_file.flush()
                extra_vars["key_file"] = key_file.name
                key_password = inputs.get("ssh_key_unlock")

        if gpg_credential:
            gpg_inputs = inputs_from_store(
                gpg_credential.inputs.get_secret_value()
            )
            gpg_key = gpg_inputs.get("gpg_public_key")
            gpg_key_file = tempfile.NamedTemporaryFile("w+t")
            gpg_key_file.write(gpg_key)
            gpg_key_file.write("\n")
            gpg_key_file.flush()
            extra_vars["verify_commit"] = "true"
            gpg_home_dir = tempfile.TemporaryDirectory()
            env_vars["GNUPGHOME"] = gpg_home_dir.name

        if not verify_ssl:
            extra_vars["ssl_no_verify"] = "true"

        extra_vars["scm_url"] = final_url
        if branch:
            extra_vars["scm_branch"] = branch
        if refspec:
            extra_vars["scm_refspec"] = refspec
        if depth:
            extra_vars["depth"] = depth
        if proxy:
            env_vars["http_proxy"] = proxy
            env_vars["https_proxy"] = proxy
            env_vars["HTTP_PROXY"] = proxy
            env_vars["HTTPS_PROXY"] = proxy

        logger.info("Cloning repository: %s", url)
        try:
            if key_password:
                cls.decrypt_key_file(key_file.name, key_password)
            if gpg_key_file:
                cls.add_gpg_key(gpg_key_file.name, gpg_home_dir.name)
            with contextlib.chdir(path):
                git_hash = _executor(extra_vars=extra_vars, env_vars=env_vars)
        except ScmError as e:
            msg = str(e)
            if secret:
                msg = msg.replace(secret, "****", 1)
                msg = msg.replace(quote(secret), "****", 1)
            logger.warning("SCM clone failed: %s", msg)
            raise ScmError(msg) from None
        finally:
            if key_file:
                key_file.close()
            if gpg_key_file:
                gpg_key_file.close()
                gpg_home_dir.cleanup()
        instance = cls(path, _executor=_executor)
        instance.git_hash = git_hash
        return instance

    @classmethod
    def build_url(
        cls, url: str, user: str, password: str, ssh_key: str
    ) -> str:
        result = urlparse(url)
        domain = result.netloc.split("@")[-1]
        scheme = result.scheme
        path = result.path

        if ssh_key and scheme == "" and path.startswith("git@"):
            return url

        if user and password:
            encoded_user = quote(user)
            encoded_password = quote(password)
            domain = f"{encoded_user}:{encoded_password}@{domain}"
        elif password:
            encoded_token = quote(password)
            domain = f"{encoded_token}@{domain}"

        unparsed = (
            scheme,
            domain,
            path,
            result.params,
            result.query,
            result.fragment,
        )
        return urlunparse(unparsed)

    @classmethod
    def decrypt_key_file(cls, key_file: str, password: str) -> None:
        result = subprocess.run(
            [KEYGEN_COMMAND, "-p", "-P", password, "-N", "", "-f", key_file],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to load key using the passphrase. Exit code "
                f"{result.returncode}: {result.stderr} {result.stdout}"
            )
            msg = "Failed to decrypt the private key using the passphrase"
            raise ScmError(msg)

    @classmethod
    def add_gpg_key(cls, key_file: str, home_dir: str) -> None:
        result = subprocess.run(
            [GPG_COMMAND, "--import", key_file],
            capture_output=True,
            text=True,
            env={"GNUPGHOME": home_dir},
        )
        if result.returncode != 0:
            logger.error(
                f"gpg import failed with exit code {result.returncode}: "
                f"{result.stderr} {result.stdout}"
            )
            msg = "Failed to import the gpg public key. Is the key valid?"
            raise ScmError(msg)


class GitAnsibleRunnerExecutor:
    ERROR_PREFIX = "Failed to clone the project:"

    def __call__(
        self,
        extra_vars: dict,
        env_vars: dict,
    ):
        with tempfile.TemporaryDirectory(prefix="EDA_RUNNER") as data_dir:
            outputs = io.StringIO()
            with contextlib.redirect_stdout(outputs):
                runner = ansible_runner.run(
                    private_data_dir=data_dir,
                    playbook=PLAYBOOK,
                    extravars=extra_vars,
                    envvars=env_vars,
                )

            if runner.rc == 0:
                match = re.search(
                    r'"msg": "Repository Version ([0-9a-fA-F]+)"',
                    outputs.getvalue(),
                )
                if match:
                    return match.group(1)
            match = re.search(
                r'fatal: \[localhost\]: FAILED! => \{.+"msg": (.+)\}',
                outputs.getvalue(),
            )
            if match:
                err_msg = match.group(1)
                if "Authentication failed" in err_msg:
                    raise ScmAuthenticationError("Authentication failed")
                if (
                    "could not read Username" in err_msg
                    or "could not read Password" in err_msg
                ):
                    err_msg = "Credentials not provided or incorrect"
                    raise ScmAuthenticationError(err_msg)
                raise ScmError(f"{self.ERROR_PREFIX} {err_msg}")
            raise ScmError(f"{self.ERROR_PREFIX} {outputs.getvalue().strip()}")
