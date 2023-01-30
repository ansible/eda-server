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
import subprocess
from typing import Final, List, Optional

from .common import StrPath

logger = logging.getLogger(__name__)

GIT_BIN: Final = shutil.which("git")
GIT_CLONE_TIMEOUT: Final = 30
GIT_TIMEOUT: Final = 30
GIT_ENVIRON: Final = {
    "GIT_TERMINAL_PROMPT": "0",
}


class GitCommandFailed(Exception):
    pass


def git_command(
    args: List[str],
    *,
    timeout: Optional[float] = None,
    cwd: Optional[StrPath] = None,
) -> subprocess.CompletedProcess:
    """Git command wrapper."""
    try:
        result = subprocess.run(
            args,
            check=True,
            encoding="utf-8",
            env=GIT_ENVIRON,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        logging.warning("%s", str(exc))
        raise GitCommandFailed("timeout")
    except subprocess.CalledProcessError as exc:
        message = (
            f"Command returned non-zero exit status {exc.returncode}:"
            f"\n\tcommand: {exc.cmd}"
            f"\n\tstderr: {exc.stderr}"
        )
        logger.warning("%s", message)
        raise GitCommandFailed(exc.stderr)
    return result


def git_shallow_clone(url: str, path: StrPath) -> None:
    """Create a shallow clone of the repository in the specified directory.

    :param url: The repository URL to clone from.
    :param path: The directory to clone into.
    :raises GitCommandFailed: If git returns non-zero exit code.
    """
    cmd = [GIT_BIN, "clone", "--quiet", "--depth", "1", url, os.fspath(path)]
    git_command(cmd)


def git_current_commit(path: os.PathLike) -> str:
    """Return the object name of the current commit.

    :param path: Path to the repository.
    :return: Current commit id.
    :raises GitCommandFailed: If git returns non-zero exit code.
    """
    cmd = [GIT_BIN, "rev-parse", "HEAD"]
    result = git_command(cmd, cwd=path)
    return result.stdout.strip()
