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

import logging
import os
import shutil
import tempfile
from typing import Iterable, Optional
from urllib.parse import urlparse, urlunparse

import pexpect

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


PLAYBOOK_COMMAND = shutil.which("ansible-playbook")
if PLAYBOOK_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find ansible-playbook executable")
PLAYBOOK = f"{os.path.dirname(os.path.abspath(__file__))}/../../playbooks/project_clone.yml"  # noqa E501

KEYGEN_COMMAND = shutil.which("ssh-keygen")
if KEYGEN_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find ssh-keygen executable")

GPG_COMMAND = shutil.which("gpg2")
if GPG_COMMAND is None:
    GPG_COMMAND = shutil.which("gpg")
if GPG_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find gpg executable")


class ScmRepository:
    """Represents a SCM repository."""

    def __init__(
        self,
        root: StrPath,
        *,
        _executor: Optional[PlaybookExecutor] = None,
    ):
        """
        Create an instance for existing repository.

        :param root: Repository root directory.
        :param _executor: Optional command executor.
        """
        self.root = root
        if _executor is None:
            _executor = PlaybookExecutor()
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
        _executor: Optional[PlaybookExecutor] = None,
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
            _executor = PlaybookExecutor()

        vars = [f"project_path={path}"]
        final_url = url
        secret = ""
        key_file = None
        gpg_key_file = None
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
                key_file.flush()
                vars.append(f"key_file={key_file.name}")
                key_password = inputs.get("ssh_key_unlock")
                if key_password:
                    cls.decrypt_key_file(key_file.name, key_password)

        if gpg_credential:
            gpg_inputs = inputs_from_store(
                gpg_credential.inputs.get_secret_value()
            )
            gpg_key = gpg_inputs.get("gpg_public_key")
            gpg_key_file = tempfile.NamedTemporaryFile("w+t")
            gpg_key_file.write(gpg_key)
            gpg_key_file.flush()
            vars.append("verify_commit=true")
            cls.add_gpg_key(gpg_key_file.name)

        if not verify_ssl:
            _executor.ENVIRON["GIT_SSL_NO_VERIFY"] = "true"

        vars.append(f"scm_url={final_url}")
        if branch:
            vars.append(f"scm_branch={branch}")
        if refspec:
            vars.append(f"scm_refspec={refspec}")
        if depth:
            vars.append(f"depth={depth}")

        vars_str = " ".join(vars)

        cmd = ["-e", f"'{vars_str}'", "-t", "update_git"]
        logger.info("Cloning repository: %s", url)
        try:
            git_hash = _executor(cmd)
        except ScmError as e:
            msg = str(e)
            if secret:
                msg = msg.replace(secret, "****", 1)
            logger.warning("SCM clone failed: %s", msg)
            raise ScmError(msg) from None
        finally:
            if key_file:
                key_file.close()
            if gpg_key_file:
                gpg_key_file.close()
        instance = cls(path, _executor=_executor)
        instance.git_hash = git_hash
        return instance

    def _execute_cmd(self, cmd: Iterable[str]):
        return self._executor(cmd, cwd=self.root)

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
        elif user and password:
            domain = f"{user}:{password}@{domain}"

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
        cmd = f'{KEYGEN_COMMAND} -p -P {password} -N "" -f {key_file}'
        child = pexpect.spawn(cmd)
        index = child.expect(["Failed to load key", pexpect.EOF])
        if index == 0:
            raise ScmError("Incorrect passhprase for the private key")

    @classmethod
    def add_gpg_key(cls, key_file: str) -> None:
        cmd = f"{GPG_COMMAND} --import {key_file}"
        pexpect.run(cmd)


class PlaybookExecutor:
    ENVIRON = {"GIT_TERMINAL_PROMPT": "0"}
    ERROR_PREFIX = "Failed to clone the project:"

    def __call__(
        self,
        args: Iterable[str],
        timeout: Optional[float] = 30,
        cwd: Optional[StrPath] = None,
    ):
        try:
            cmd = f"{PLAYBOOK_COMMAND} {' '.join(args)} {PLAYBOOK}"
            child = pexpect.spawn(
                cmd,
                env=os.environ | PlaybookExecutor.ENVIRON,
                timeout=timeout,
                cwd=cwd,
            )
            index = child.expect(
                [
                    '"msg": "Repository Version ',
                    "fatal: \\[localhost\\]: ",
                    pexpect.EOF,
                ]
            )
            if index == 0:
                line = child.readline().decode()
                return line.split('"')[0]
            elif index == 1:
                line = child.readline().decode()
                if "could not read Username" in line:
                    raise ScmAuthenticationError("Credentials not provided")
                raise ScmError(f"{self.ERROR_PREFIX} {line}")
            raise ScmError(f"{self.ERROR_PREFIX} {child.before}")
        except pexpect.exceptions.TIMEOUT:
            raise ScmError(f"{self.ERROR_PREFIX} command timeout.")
        except pexpect.exceptions.ExceptionPexpect as e:
            raise ScmError(f"{self.ERROR_PREFIX} {str(e)}") from e
