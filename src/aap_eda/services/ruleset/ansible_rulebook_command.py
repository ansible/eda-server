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
import shutil
import subprocess
from typing import Final, List, Optional

logger = logging.getLogger(__name__)

ANSIBLE_RULEBOOK_BIN: Final = shutil.which("ansible-rulebook")
SSH_AGENT_BIN: Final = shutil.which("ssh-agent")


class AnsibleRulebookCommandFailed(Exception):
    pass


def ansible_rulebook_command(
    args: List[str],
    *,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """ansible-rulebook command wrapper."""
    if ANSIBLE_RULEBOOK_BIN is None:
        raise AnsibleRulebookCommandFailed(
            "ansible-rulebook: command not found"
        )

    if SSH_AGENT_BIN is None:
        raise AnsibleRulebookCommandFailed("ssh-agent: command not found")

    logger.info(f"args: {args}")

    try:
        result = subprocess.run(
            [SSH_AGENT_BIN, ANSIBLE_RULEBOOK_BIN, *args],
            check=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        logging.warning("%s", str(exc))
        raise AnsibleRulebookCommandFailed("timeout")
    except subprocess.CalledProcessError as exc:
        message = (
            f"Command returned non-zero exit status {exc.returncode}:"
            f"\n\tcommand: {exc.cmd}"
            f"\n\tstderr: {exc.stderr}"
        )
        logger.warning("%s", message)
        raise AnsibleRulebookCommandFailed(exc.stderr)

    return result
