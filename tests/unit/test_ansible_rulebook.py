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
import re
import subprocess
from unittest import mock

import pytest

from aap_eda.services.ruleset.ansible_rulebook import (
    AnsibleRulebookService,
    AnsibleRulebookServiceFailed,
)


@mock.patch("subprocess.run")
def test_run_worker_mode(run_mock: mock.Mock):
    AnsibleRulebookService().run_worker_mode(
        "ssh-agent",
        "ansible-rulebook",
        "ws://localhost:8000",
        "no",
        "1",
    )

    run_mock.assert_called_once_with(
        [
            "ssh-agent",
            "ansible-rulebook",
            "--worker",
            "--websocket-address",
            "ws://localhost:8000",
            "--websocket-ssl-verify",
            "no",
            "--id",
            "1",
        ],
        check=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=None,
    )


@mock.patch("subprocess.run")
def test_raise_error(run_mock: mock.Mock):
    def raise_error(cmd, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=128, cmd=cmd, stderr="fatal: ansible-rulebook crashed"
        )

    run_mock.side_effect = raise_error

    with pytest.raises(
        AnsibleRulebookServiceFailed,
        match=re.escape("fatal: ansible-rulebook crashed"),
    ):
        AnsibleRulebookService().run_worker_mode(
            "ssh-agent",
            "ansible-rulebook",
            "ws://localhost:8000",
            "no",
            "1",
        )
