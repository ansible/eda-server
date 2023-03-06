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
from typing import Final, Optional

logger = logging.getLogger(__name__)

ANSIBLE_RULEBOOK_BIN: Final = shutil.which("ansible-rulebook")
SSH_AGENT_BIN: Final = shutil.which("ssh-agent")


class AnsibleRulebookServiceFailed(Exception):
    pass


class AnsibleRulebookService:
    def __init__(self, cwd: Optional[str] = None):
        self.cwd = cwd

    def run_worker_mode(
        self,
        url: str,
        activation_id: str,
    ) -> subprocess.CompletedProcess:
        """Run ansible-rulebook in worker mode."""
        args = [
            "--worker",
            "--websocket-address",
            url,
            "--id",
            str(activation_id),
        ]

        if ANSIBLE_RULEBOOK_BIN and SSH_AGENT_BIN:
            try:
                # TODO: subprocess.run may run a while and will block the
                # following DB updates. Need to find a better way to solve it.
                return subprocess.run(
                    [SSH_AGENT_BIN, ANSIBLE_RULEBOOK_BIN, *args],
                    check=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=self.cwd,
                )
            except subprocess.CalledProcessError as exc:
                message = (
                    f"Command returned non-zero exit status {exc.returncode}:"
                    f"\n\tcommand: {exc.cmd}"
                    f"\n\tstderr: {exc.stderr}"
                )
                logger.warning("%s", message)
                raise AnsibleRulebookServiceFailed(exc.stderr)
        else:
            message = (
                f"Commands: SSH_AGENT_BIN[{SSH_AGENT_BIN}] "
                f"or ANSIBLE_RULEBOOK_BIN [{ANSIBLE_RULEBOOK_BIN}] not found"
            )
            raise AnsibleRulebookServiceFailed(message)
