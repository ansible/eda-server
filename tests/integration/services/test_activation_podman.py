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
import base64
import json
import os
import tempfile
from unittest import mock

import pytest
from django.conf import settings
from podman.errors import exceptions

from aap_eda.core import models
from aap_eda.core.enums import CredentialType
from aap_eda.services.ruleset.activation_db_logger import ActivationDbLogger
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
    user = models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )
    activation = models.Activation.objects.create(
        name="activation",
        user=user,
    )
    activation_instance = models.ActivationInstance.objects.create(
        name="test-instance",
        activation=activation,
    )

    return (credential, decision_environment, activation_instance)


@pytest.fixture(autouse=True)
def use_dummy_log_level(settings):
    settings.ANSIBLE_RULEBOOK_LOG_LEVEL = "-vv"


@pytest.fixture(autouse=True)
def use_dummy_env_vars(settings):
    settings.PODMAN_ENV_VARS = {"A": "1", "B": 2}


@pytest.fixture(autouse=True)
def use_dummy_mem_limit(settings):
    settings.PODMAN_MEM_LIMIT = "500m"


@pytest.fixture(autouse=True)
def use_dummy_mounts(settings):
    settings.PODMAN_MOUNTS = [
        {
            "type": "bind",
            "source": "/a",
            "target": "/b/certs",
            "read_only": True,
            "relabel": "Z",
        }
    ]


@pytest.fixture(autouse=True)
def use_podman_extra_args(settings):
    settings.PODMAN_EXTRA_ARGS = {"user": 1001, "userns_mode": "keep-id"}


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman(my_mock: mock.Mock, init_data):
    credential, decision_environment, activation_instance = init_data
    client_mock = mock.Mock()
    my_mock.return_value = client_mock
    activation_db_logger = ActivationDbLogger(activation_instance.id)

    podman = ActivationPodman(decision_environment, None, activation_db_logger)

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
    credential, decision_environment, activation_instance = init_data
    client_mock = mock.Mock()
    client_mock.containers.run.return_value.logs.return_value = iter(
        [
            b"test_output_line_1",
            b"test_output_line_2",
        ]
    )
    client_mock.containers.run.return_value.wait.return_value = 0
    client_mock.containers.run.return_value.id = "containerid"

    my_mock.return_value = client_mock

    activation_db_logger = ActivationDbLogger(activation_instance.id)
    podman = ActivationPodman(decision_environment, None, activation_db_logger)
    uuid_mock.return_value = DUMMY_UUID
    ports = {"5000/tcp": 5000}

    assert models.ActivationInstanceLog.objects.count() == 2

    podman.run_worker_mode(
        ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
        ws_ssl_verify="no",
        activation_instance=activation_instance,
        heartbeat=5,
        ports=ports,
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
            str(activation_instance.id),
            "--heartbeat",
            "5",
            settings.ANSIBLE_RULEBOOK_LOG_LEVEL,
        ],
        stdout=True,
        stderr=True,
        remove=True,
        detach=True,
        name=f"eda-{activation_instance.id}-{DUMMY_UUID}",
        ports=ports,
        mem_limit=settings.PODMAN_MEM_LIMIT,
        mounts=settings.PODMAN_MOUNTS,
        environment=settings.PODMAN_ENV_VARS,
        user=1001,
        userns_mode="keep-id",
    )

    activation_db_logger.flush()

    assert models.ActivationInstanceLog.objects.count() == 8


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman_with_invalid_credential(
    my_mock: mock.Mock, init_data
):
    def raise_error(*args, **kwargs):
        raise exceptions.APIError(
            message="login attempt failed with status: 401 Unauthorized"
        )

    credential, decision_environment, activation_instance = init_data
    client_mock = mock.Mock()
    my_mock.return_value = client_mock

    client_mock.login.side_effect = raise_error
    activation_db_logger = ActivationDbLogger(activation_instance.id)

    with pytest.raises(exceptions.APIError, match="login attempt failed"):
        ActivationPodman(decision_environment, None, activation_db_logger)


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman_with_invalid_ports(my_mock: mock.Mock, init_data):
    def raise_error(*args, **kwargs):
        raise exceptions.APIError(message="bind: address already in use")

    credential, decision_environment, activation_instance = init_data
    client_mock = mock.Mock()
    my_mock.return_value = client_mock

    client_mock.containers.run.side_effect = raise_error
    activation_db_logger = ActivationDbLogger(activation_instance.id)

    podman = ActivationPodman(decision_environment, None, activation_db_logger)
    with pytest.raises(
        exceptions.APIError, match="bind: address already in use"
    ):
        podman.run_worker_mode(
            ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
            ws_ssl_verify="no",
            activation_instance=activation_instance,
            heartbeat=5,
            ports={"5000/tcp": 5000},
        )


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman_with_auth_json(my_mock: mock.Mock, init_data):
    credential, decision_environment, activation_instance = init_data
    data = f"{credential.username}:{credential.secret.get_secret_value()}"
    encoded_data = data.encode("ascii")
    auth_key_value = base64.b64encode(encoded_data).decode("ascii")
    client_mock = mock.Mock()
    my_mock.return_value = client_mock
    client_mock.containers.run.return_value.logs.return_value = iter(
        [
            b"test_output_line_1",
            b"test_output_line_2",
        ]
    )
    client_mock.containers.run.return_value.wait.return_value = 0
    client_mock.containers.run.return_value.id = "containerid"

    activation_db_logger = ActivationDbLogger(activation_instance.id)

    with tempfile.TemporaryDirectory() as tmpdirname:
        containers_dir = os.path.join(tmpdirname, "containers")
        os.makedirs(containers_dir)
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmpdirname}):
            podman = ActivationPodman(
                decision_environment, None, activation_db_logger
            )
            podman.run_worker_mode(
                ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
                ws_ssl_verify="no",
                activation_instance=activation_instance,
                heartbeat=5,
                ports={"5000/tcp": 5000},
            )
            with open(os.path.join(containers_dir, "auth.json")) as f:
                auth_dict = json.load(f)
                assert auth_dict["auths"]["quay.io"]["auth"] == auth_key_value


@pytest.mark.django_db
@mock.patch("aap_eda.services.ruleset.activation_podman.PodmanClient")
def test_activation_podman_with_existing_auth_json(
    my_mock: mock.Mock, init_data
):
    credential, decision_environment, activation_instance = init_data
    data = f"{credential.username}:{credential.secret.get_secret_value()}"
    encoded_data = data.encode("ascii")
    auth_key_value = base64.b64encode(encoded_data).decode("ascii")
    client_mock = mock.Mock()
    my_mock.return_value = client_mock
    client_mock.containers.run.return_value.logs.return_value = iter(
        [
            b"test_output_line_1",
            b"test_output_line_2",
        ]
    )
    client_mock.containers.run.return_value.wait.return_value = 0
    client_mock.containers.run.return_value.id = "containerid"

    activation_db_logger = ActivationDbLogger(activation_instance.id)
    old_key = "gobbledegook"
    old_data = {
        "auths": {"dummy": {"auth": old_key}, "quay.io": {"auth": old_key}}
    }

    with tempfile.TemporaryDirectory() as tmpdirname:
        containers_dir = os.path.join(tmpdirname, "containers")
        os.makedirs(containers_dir)

        with open(os.path.join(containers_dir, "auth.json"), "w") as f:
            json.dump(old_data, f, indent=6)

        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmpdirname}):
            podman = ActivationPodman(
                decision_environment, None, activation_db_logger
            )
            podman.run_worker_mode(
                ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
                ws_ssl_verify="no",
                activation_instance=activation_instance,
                heartbeat=5,
                ports={"5000/tcp": 5000},
            )
            with open(os.path.join(containers_dir, "auth.json")) as f:
                auth_dict = json.load(f)
                assert auth_dict["auths"]["quay.io"]["auth"] == auth_key_value
                assert auth_dict["auths"]["dummy"]["auth"] == old_key
