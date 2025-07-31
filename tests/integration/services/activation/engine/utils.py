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
"""Common Utilities for Engine Tests."""

from dataclasses import dataclass

from aap_eda.core import models
from aap_eda.core.enums import ImagePullPolicy
from aap_eda.services.activation.engine.common import (
    AnsibleRulebookCmdLine,
    ContainerRequest,
    Credential,
)


@dataclass
class InitData:
    activation: models.Activation
    activation_instance: models.RulebookProcess


def get_ansible_rulebook_cmdline(data: InitData):
    return AnsibleRulebookCmdLine(
        ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
        ws_ssl_verify="no",
        ws_token_url="http://localhost:8000/api/eda/v1/auth/token/refresh",
        ws_access_token="access",
        ws_refresh_token="refresh",
        id=data.activation.id,
        log_level="-v",
        heartbeat=5,
    )


def get_request(
    data: InitData,
    username: str,
    default_organization: models.Organization,
    image_url: str = "quay.io/ansible/ansible-rulebook:main",
    **kwargs,
):
    return ContainerRequest(
        name="test-request",
        image_url=image_url,
        rulebook_process_id=data.activation_instance.id,
        process_parent_id=data.activation.id,
        cmdline=get_ansible_rulebook_cmdline(data),
        credential=Credential(
            username=username,
            secret="secret",
            ssl_verify=True,
            organization=default_organization,
        ),
        ports=[("localhost", 8080)],
        mem_limit="8G",
        env_vars={"a": 1},
        extra_args={"b": 2},
        pull_policy=ImagePullPolicy.ALWAYS.value,
        **kwargs,
    )
