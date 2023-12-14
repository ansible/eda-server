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

import io
import logging
import os
import shutil
import subprocess
from typing import IO, Final, Iterable, Optional, Union

from aap_eda.core.models import Credential
from aap_eda.core.types import StrPath

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Git command error."""

    pass


class GitAuthenticationError(Exception):
    """Git Authentication error."""

    pass


class ExecutableNotFoundError(Exception):
    """Executable Not Found error."""

    pass


GIT_COMMAND = shutil.which("git")
if GIT_COMMAND is None:
    raise ExecutableNotFoundError("Cannot find git executable")


class GitRepository:
    """Represents a git repository."""

    def __init__(
        self,
        root: StrPath,
        *,
        _executor: Optional[GitExecutor] = None,
    ):
        """
        Create an instance for existing repository.

        :param root: Repository root directory.
        :param _executor: Optional command executor.
        """
        self.root = root
        if _executor is None:
            _executor = GitExecutor()
        self._executor = _executor

    def rev_parse(self, rev: str) -> str:
        """
        Return object identifier for the given revision specifier.

        :param rev: Revision specifier, typically names a commit object.
        :return: Git object identifier
        """
        cmd = ["rev-parse", rev]
        result = self._execute_cmd(cmd)
        return result.stdout.strip()

    def archive(
        self,
        treeish: str,
        /,
        output: [StrPath, io.BytesIO],
        *,
        format: Optional[str] = None,
    ) -> None:
        """Create an archive of files from a repository."""
        cmd = ["archive"]
        kwargs = {"cwd": self.root}
        if isinstance(output, (str, os.PathLike)):
            cmd.extend(("--output", os.fspath(output)))
        else:
            kwargs["stdout"] = output
        if format is not None:
            cmd.extend(("--format", format))
        cmd.append(treeish)
        self._executor(cmd, **kwargs)

    @classmethod
    def clone(
        cls,
        url: str,
        path: StrPath,
        *,
        credential: Optional[Credential] = None,
        depth: Optional[int] = None,
        verify_ssl: bool = True,
        _executor: Optional[GitExecutor] = None,
    ) -> GitRepository:
        """
        Clone a repository from url into target path.

        :param url: The repository URL to clone from.
        :param path: The directory to clone into.
        :param depth: If set, creates a shallow clone with a history truncated
            to the specified number of commits.
        :param verify_ssl: Indicates if SSL verification is enabled.
        :param _executor: Optional command executor.
        :return:
        """
        if _executor is None:
            _executor = GitExecutor()

        final_url = url
        secret = ""
        if credential:
            secret = credential.secret.get_secret_value()
            # TODO(alex): encapsulate url composition
            index = 0
            if url.startswith("https://"):
                index = 8
            elif url.startswith("http://"):
                index = 7
            if index > 0:
                # user can be optional
                user_part = (
                    f"{credential.username}:" if credential.username else ""
                )
                final_url = f"{url[:index]}{user_part}{secret}@{url[index:]}"

        if not verify_ssl:
            _executor.ENVIRON["GIT_SSL_NO_VERIFY"] = "true"

        cmd = ["clone", "--quiet"]
        if depth is not None:
            cmd.extend(["--depth", str(depth)])
        cmd.extend([final_url, os.fspath(path)])
        logger.info("Cloning repository: %s", url)
        try:
            _executor(cmd)
        except GitError as e:
            msg = str(e)
            if secret:
                msg = msg.replace(secret, "****", 1)
            logger.warning("Git clone failed: %s", msg)
            raise GitError(msg) from None
        return cls(path, _executor=_executor)

    def _execute_cmd(self, cmd: Iterable[str]):
        return self._executor(cmd, cwd=self.root)


class GitExecutor:
    DEFAULT_TIMEOUT: Final = 120
    ENVIRON: dict = {
        "GIT_TERMINAL_PROMPT": "0",
    }

    def __call__(
        self,
        args: Iterable[str],
        timeout: Optional[float] = None,
        cwd: Optional[StrPath] = None,
        stdout: Union[IO, int, None] = None,
    ):
        if stdout is None:
            stdout = subprocess.PIPE
        stderr = subprocess.PIPE

        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        try:
            return subprocess.run(
                [GIT_COMMAND, *args],
                check=True,
                encoding="utf-8",
                env=self.ENVIRON,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired as e:
            logger.warning("%s", str(e))
            raise GitError(str(e)) from e
        except subprocess.CalledProcessError as e:
            if "Authentication failed" in e.stderr:
                raise GitAuthenticationError("Authentication failed") from None
            if "could not read Username" in e.stderr:
                raise GitAuthenticationError(
                    "Credentials not provided"
                ) from None
            # generic error
            usr_msg = f"Command git failed with return code {e.returncode}."
            if e.stderr:
                usr_msg += f" Error: {e.stderr}"
            raise GitError(usr_msg) from None
