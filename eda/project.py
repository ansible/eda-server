#  Copyright 2022 Red Hat, Inc.
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

import asyncio
import logging
import shutil
import tempfile

from . import tuples
from .utils import subprocess as subprocess_utils

logger = logging.getLogger("eda_server")

GIT_BIN = shutil.which("git")
TAR_BIN = shutil.which("tar")

GIT_CLONE_TIMEOUT = 30
GIT_TIMEOUT = 10
GIT_ENVIRON = {
    "GIT_TERMINAL_PROMPT": "0",
}


class GitCommandFailed(Exception):
    pass


async def run_git_command(*cmd, **kwargs):
    try:
        result = await subprocess_utils.run(
            *cmd,
            check=True,
            encoding="utf-8",
            env=GIT_ENVIRON,
            **kwargs,
        )
    except subprocess_utils.TimeoutExpired as exc:
        logging.warning("%s", str(exc))
        raise GitCommandFailed("timeout")
    except subprocess_utils.CalledProcessError as exc:
        message = (
            f"Command returned non-zero exit status {exc.returncode}:"
            f"\n\tcommand: {exc.cmd}"
            f"\n\tstderr: {exc.stderr}"
        )
        logging.warning("%s", message)
        raise GitCommandFailed(exc.stderr)
    return result


async def git_clone(url: str, dest: str) -> None:
    """
    Clone repository into the specified directory.

    :param url: The repository to clone from.
    :param dest: The directory to clone into.
    :raises GitError: If git returns non-zero exit code.
    """
    cmd = [GIT_BIN, "clone", "--quiet", url, dest]
    await run_git_command(
        *cmd,
        cwd=dest,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        timeout=GIT_CLONE_TIMEOUT,
    )


async def git_get_current_commit(repo: str) -> str:
    """
    Return id of the current commit.

    :param repo: Path to the repository.
    :return: Current commit id.
    """
    cmd = [GIT_BIN, "rev-parse", "HEAD"]
    result = await run_git_command(
        *cmd,
        cwd=repo,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        timeout=GIT_TIMEOUT,
    )
    return result.stdout.strip()


async def import_project(data: tuples.Project):
    print(data)
    with tempfile.TemporaryDirectory(prefix="eda-import-project") as repo_dir:
        commit_id = await clone_project(data.url, repo_dir)
        print(commit_id)
        project = None
        return project


async def clone_project(url: str, dest: str):
    await git_clone(url, dest)
    return await git_get_current_commit(dest)
