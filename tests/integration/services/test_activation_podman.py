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
import os
from unittest import mock

import pytest
from podman.errors import exceptions

from aap_eda.core import models
from aap_eda.core.enums import CredentialType
from aap_eda.services.ruleset.activation_podman import ActivationPodman

DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"


@pytest.fixture()
def init_data():
    credential = models.Credential.objects.create(
        name="test-credential",
        username="adam",
        secret="secret",
        credential_type=CredentialType.REGISTRY,
    )
    credential.refresh_from_db()
    decision_environment = models.DecisionEnvironment.objects.create(
        name="de",
        image_url="quay.io/ansible/ansible-rulebook:main",
        credential=credential,
    )

    return (credential, decision_environment)


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman(my_mock: mock.Mock, init_data):
    credential, decision_environment = init_data
    client_mock = mock.Mock()
    my_mock.return_value = client_mock

    podman = ActivationPodman(decision_environment, None)

    client_mock.login.assert_called_once_with(
        username="adam", password="secret", registry="quay.io"
    )
    assert (
        podman.podman_url
        == f"unix:///run/user/{os.getuid()}/podman/podman.sock"
    )


@pytest.mark.django_db
@mock.patch("uuid.uuid4")
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman_run_worker_mode(
    my_mock: mock.Mock, uuid_mock: mock.Mock, init_data
):
    credential, decision_environment = init_data
    client_mock = mock.Mock()
    my_mock.return_value = client_mock

    podman = ActivationPodman(decision_environment, None)
    uuid_mock.return_value = DUMMY_UUID

    podman.run_worker_mode(
        ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
        ws_ssl_verify="no",
        activation_instance_id="1",
        heartbeat="5",
    )

    client_mock.containers.run.assert_called_once_with(
        image=decision_environment.image_url,
        command=[
            "ansible-rulebook",
            "--worker",
            "--websocket-ssl-verify",
            "no",
            "--websocket-address",
            "ws://localhost:8000/api/eda/ws/ansible-rulebook",
            "--id",
            "1",
            "--heartbeat",
            "5",
        ],
        stdout=True,
        stderr=True,
        remove=True,
        detach=True,
        name=f"eda-1-{DUMMY_UUID}",
    )


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman_with_invalid_credential(
    my_mock: mock.Mock, init_data
):
    def raise_error(*args, **kwargs):
        raise exceptions.APIError(
            message="login attempt failed with status: 401 Unauthorized"
        )

    credential, decision_environment = init_data
    client_mock = mock.Mock()
    my_mock.return_value = client_mock

    client_mock.login.side_effect = raise_error

    with pytest.raises(exceptions.APIError, match="login attempt failed"):
        ActivationPodman(decision_environment, None)
