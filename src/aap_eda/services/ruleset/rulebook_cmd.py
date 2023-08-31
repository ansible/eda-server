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
from dataclasses import dataclass
from typing import Iterable, List, Union

from django.conf import settings

from .ruleset_handler import ACTIVATION_PATH


@dataclass
class RulebookCmd:
    """
    Represents ansible_rulebook command.

    Represents ansible_rulebook command and their arguments, and
    provides methods to render it for cmd runners.
    """

    program_name: str = "ansible-rulebook"
    instance_id: Union[str, int, None] = None
    verbose: bool = False
    debug: bool = False
    websocket: str = f"{settings.WEBSOCKET_BASE_URL}{ACTIVATION_PATH}"
    websocket_ssl_verify: str = settings.WEBSOCKET_SSL_VERIFY
    worker_mode: bool = True
    verbosity: int = 0
    heartbeat: int = 0

    def __post_init__(self):
        # verbosity overrides verbose and debug
        if self.verbosity > 0:
            self.verbose = False
            self.debug = False

        if settings.ANSIBLE_RULEBOOK_LOG_LEVEL:
            if settings.ANSIBLE_RULEBOOK_LOG_LEVEL == "-v":
                self.debug = True
            if settings.ANSIBLE_RULEBOOK_LOG_LEVEL == "-vv":
                self.verbose = True

    def __str__(self) -> str:
        return self.to_string()

    def __iter__(self) -> Iterable:
        return (item for item in self.to_list())

    def to_list(self) -> List:
        result = [self.program_name]

        if self.worker_mode:
            result.append("--worker")
        if self.websocket_ssl_verify:
            result.extend(
                ["--websocket-ssl-verify", self.websocket_ssl_verify]
            )
        if self.websocket:
            result.extend(["--websocket-address", self.websocket])
        if self.instance_id:
            result.extend(["--id", str(self.instance_id)])
        if self.heartbeat > 0:
            result.extend(["--heartbeat", str(self.heartbeat)])
        if self.verbose:
            result.append("-vv")
        if self.debug:
            result.append("-v")
        if self.verbosity > 0:
            result.append(f"-{'v'*self.verbosity}")

        return result

    def to_string(self) -> str:
        return " ".join(self.to_list())
