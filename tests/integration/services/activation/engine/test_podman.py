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
from pathlib import Path
from unittest import mock

import pytest
from podman import PodmanClient
from podman.errors import ContainerError, ImageNotFound
from podman.errors.exceptions import APIError, NotFound
from rq.timeouts import JobTimeoutException

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.db_log_handler import DBLogger
from aap_eda.services.activation.engine import messages
from aap_eda.services.activation.engine.common import (
    ContainerRequest,
    Credential,
)
from aap_eda.services.activation.engine.exceptions import (
    ContainerCleanupError,
    ContainerEngineError,
    ContainerEngineInitError,
    ContainerImagePullError,
    ContainerLoginError,
    ContainerNotFoundError,
    ContainerStartError,
    ContainerUpdateLogsError,
)
from aap_eda.services.activation.engine.podman import (
    Engine,
    _get_podman_socket_url,
    get_podman_client,
)
from aap_eda.settings.default import settings as orig_dynaconf_settings

from .utils import InitData, get_ansible_rulebook_cmdline, get_request

DATA_DIR = Path(__file__).parent / "data"


def get_request_with_never_pull_policy(
    data: InitData,
    default_organization: models.Organization,
):
    return ContainerRequest(
        name="test-request",
        image_url="quay.io/ansible/ansible-rulebook:main",
        rulebook_process_id=data.activation_instance.id,
        process_parent_id=data.activation.id,
        cmdline=get_ansible_rulebook_cmdline(data),
        pull_policy="Never",
        credential=Credential(
            username="me",
            secret="secret",
            ssl_verify=True,
            organization=default_organization,
        ),
    )


def get_request_with_credential(
    default_organization: models.Organization,
    data: InitData,
):
    return ContainerRequest(
        name="test-request",
        image_url="quay.io/ansible/ansible-rulebook:main",
        rulebook_process_id=data.activation_instance.id,
        process_parent_id=data.activation.id,
        cmdline=get_ansible_rulebook_cmdline(data),
        credential=Credential(
            username="me",
            secret="secret",
            ssl_verify=True,
            organization=default_organization,
        ),
    )


@pytest.fixture(autouse=True)
def use_dummy_socket_url(settings):
    settings.PODMAN_SOCKET_URL = "unix://socket_url"


@pytest.fixture
def podman_engine(init_podman_data):
    activation_id = init_podman_data.activation.id
    with mock.patch(
        "aap_eda.services.activation.engine.podman.PodmanClient"
    ) as client_mock:
        engine = Engine(
            _activation_id=str(activation_id),
            client=client_mock,
        )

        yield engine


def test_podman_socket_url_from_settings(settings):
    """Test when PODMAN_SOCKET_URL is set in settings."""
    settings.PODMAN_SOCKET_URL = "custom_socket_url"
    result = _get_podman_socket_url()
    assert result == "custom_socket_url"


def test_podman_socket_url_as_root(settings):
    """Test when the user is root (uid=0)."""
    settings.PODMAN_SOCKET_URL = None
    with mock.patch("os.getuid", return_value=0):
        result = _get_podman_socket_url()
        assert result == "unix:///run/podman/podman.sock"


def test_podman_socket_url_non_root_with_xdg_runtime_dir(settings):
    """Test for a non-root user with XDG_RUNTIME_DIR set."""
    settings.PODMAN_SOCKET_URL = None
    with mock.patch("os.getuid", return_value=1000), mock.patch(
        "os.getenv",
        return_value="/custom/runtime/dir",
    ):
        result = _get_podman_socket_url()
        assert result == "unix:///custom/runtime/dir/podman/podman.sock"


@mock.patch.dict(os.environ, clear=True)
def test_podman_socket_url_non_root_without_xdg_runtime_dir(settings):
    """Test for a non-root user without XDG_RUNTIME_DIR set."""
    settings.PODMAN_SOCKET_URL = None
    with mock.patch("os.getuid", return_value=1000):
        result = _get_podman_socket_url()
        assert result == "unix:///run/user/1000/podman/podman.sock"


def test_get_podman_client_with_timeout(settings):
    """Test setting the timeout for the Podman client."""
    settings.PODMAN_SOCKET_TIMEOUT = 10
    client = get_podman_client()
    assert client.api.timeout == 10


def test_get_podman_client_with_zero_timeout():
    """Test setting the timeout for the Podman client to zero."""
    with mock.patch("aap_eda.settings.default.settings.get") as get_mock:

        def get_side_effect(*args, **kwargs):
            if args[0] == "PODMAN_SOCKET_TIMEOUT":
                return 0
            return orig_dynaconf_settings.get(*args, **kwargs)

        get_mock.side_effect = get_side_effect
        client = get_podman_client()
        assert client.api.timeout is None


def test_get_podman_client(settings):
    settings.PODMAN_SOCKET_URL = None
    uid_0_mock = mock.Mock(return_value=0)

    with mock.patch("os.getuid", uid_0_mock):
        client = get_podman_client()
        assert client.api.base_url.netloc == "%2Frun%2Fpodman%2Fpodman.sock"

    client = get_podman_client()
    xdg_runtime_dir = os.getenv(
        "XDG_RUNTIME_DIR", f"%2Frun%2Fuser%2F{os.getuid()}"
    )
    # Replace any '/'s from XDG_RUNTIME_DIR.
    xdg_runtime_dir = xdg_runtime_dir.replace("/", "%2F")

    assert (
        client.api.base_url.netloc
        == f"{xdg_runtime_dir}%2Fpodman%2Fpodman.sock"
    )


def test_get_podman_client_with_exception(settings):
    def raise_error(*args, **kwargs):
        raise ValueError("Failed to initialize client")

    with mock.patch.object(PodmanClient, "__init__", side_effect=raise_error):
        with pytest.raises(
            ContainerEngineInitError,
            match="Failed to initialize client",
        ):
            get_podman_client()


@pytest.mark.django_db
def test_engine_init(init_podman_data):
    activation_id = init_podman_data.activation.id
    with mock.patch("aap_eda.services.activation.engine.podman.PodmanClient"):
        engine = Engine(_activation_id=str(activation_id))
        engine.client.version.assert_called_once()


@pytest.mark.django_db
def test_engine_init_with_exception(init_podman_data):
    activation_id = init_podman_data.activation.id
    with pytest.raises(
        ContainerEngineInitError,
        match=r"http://socket_url/",
    ):
        Engine(_activation_id=str(activation_id))


@pytest.mark.django_db
def test_engine_start(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    request = get_request(
        init_podman_data,
        "me",
        default_organization,
        mounts=[{"/dev": "/opt"}],
    )
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    engine.start(request, log_handler)

    engine.client.containers.run.assert_called_once()
    assert models.RulebookProcessLog.objects.count() == 4
    for log in models.RulebookProcessLog.objects.all():
        assert log.log_timestamp > 0
    assert models.RulebookProcessLog.objects.last().log.endswith("is running.")


@pytest.mark.django_db
def test_engine_start_with_none_image_url(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )
    request.image_url = None

    with pytest.raises(ContainerStartError):
        engine.start(request, log_handler)


@pytest.mark.django_db
def test_engine_start_with_credential(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )
    credential = Credential(
        username="me",
        secret="secret",
        ssl_verify=True,
        organization=default_organization,
    )
    request.credential = credential

    engine.start(request, log_handler)

    engine.client.images.pull.assert_called_once_with(
        request.image_url,
        tls_verify=bool(credential.ssl_verify),
        auth_config={
            "username": credential.username,
            "password": credential.secret,
        },
    )
    engine.client.containers.run.assert_called_once_with(
        image=request.image_url,
        command=request.cmdline.command_and_args(),
        stdout=True,
        stderr=True,
        remove=True,
        detach=True,
        name=request.name,
        ports={"8080/tcp": 8080},
        mem_limit="8G",
        mounts=request.mounts,
        environment={"a": 1},
        b=2,
    )


@pytest.mark.django_db
def test_engine_start_with_login_api_exception(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    credential = Credential(
        username="me",
        secret="sec1",
        ssl_verify=True,
        organization=default_organization,
    )
    engine = podman_engine
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )
    request.credential = credential

    def raise_error(*args, **kwargs):
        raise ContainerLoginError("Login failed")

    engine.client.login.side_effect = raise_error

    with pytest.raises(ContainerLoginError, match="Login failed"):
        engine._login(request)


@pytest.mark.django_db
def test_engine_start_with_image_not_found_exception(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )

    def raise_not_found_error(*args, **kwargs):
        raise ImageNotFound("Image not found")

    engine.client.images.pull.side_effect = raise_not_found_error

    with pytest.raises(
        ContainerImagePullError, match=f"Image {request.image_url} not found"
    ):
        engine.start(request, log_handler)

    assert models.RulebookProcessLog.objects.last().log.endswith(
        f"Image {request.image_url} not found"
    )


@pytest.mark.django_db
def test_engine_start_with_image_api_exception(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )

    def raise_api_error(*args, **kwargs):
        raise APIError("Image not found")

    engine.client.images.pull.side_effect = raise_api_error

    with pytest.raises(ContainerStartError, match="Image not found"):
        engine.start(request, log_handler)


@pytest.mark.django_db
def test_engine_start_with_image_pull_timeout_exception(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )
    error = "Task exceeded maximum timeout value 120 seconds"

    def raise_timeout_error(*args, **kwargs):
        raise JobTimeoutException(error)

    engine.client.images.pull.side_effect = raise_timeout_error

    with pytest.raises(ContainerImagePullError, match=error):
        engine.start(request, log_handler)


@pytest.mark.django_db
def test_engine_start_with_image_pull_exception(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )

    image_mock = mock.Mock()
    image_mock.pull.return_value.id = None
    msg = (
        f"Image {request.image_url} pull failed. The image url "
        "or the credentials may be incorrect."
    )

    with mock.patch.object(engine.client, "images", image_mock):
        with pytest.raises(ContainerImagePullError, match=msg):
            engine.start(request, log_handler)

    assert models.RulebookProcessLog.objects.last().log.endswith(msg)


@pytest.mark.django_db
def test_engine_start_with_containers_run_exception(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    request = get_request(
        init_podman_data, "me", default_organization, mounts=[{"/dev": "/opt"}]
    )

    def raise_error(*args, **kwargs):
        raise ContainerError(
            container="container",
            exit_status=1,
            command="ansibile-rulebook",
            image="image",
        )

    engine.client.containers.run.side_effect = raise_error

    with pytest.raises(ContainerStartError, match=r"Container Start Error:"):
        engine.start(request, log_handler)

    assert (
        "Container Start Error:"
        in models.RulebookProcessLog.objects.last().log
    )


@pytest.mark.django_db
def test_engine_start_with_never_pull_policy_request(
    init_podman_data,
    podman_engine,
    default_organization: models.Organization,
):
    engine = podman_engine
    request = get_request_with_never_pull_policy(
        init_podman_data, default_organization
    )
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    engine.start(request, log_handler)

    engine.client.containers.run.assert_called_once()


@pytest.mark.django_db
def test_engine_get_status(podman_engine):
    engine = podman_engine

    container_mock = mock.Mock()
    engine.client.containers.get.return_value = container_mock

    # when status in "running"
    container_mock.status = "running"
    activation_status = engine.get_status("container_id")

    assert activation_status.status == ActivationStatus.RUNNING
    assert activation_status.message == messages.POD_RUNNING.format(
        pod_id="container_id"
    )

    # when status in "created"
    container_mock.status = "created"
    container_mock.attrs = {"State": {"Error": None}}
    activation_status = engine.get_status("container_id")

    assert activation_status.status == ActivationStatus.FAILED

    for unexpected_state in [
        "paused",
        "restarting",
        "removing",
        "dead",
        "configured",
        "unknown",
    ]:
        container_mock.status = unexpected_state
        activation_status = engine.get_status("container_id")

        assert activation_status.status == ActivationStatus.FAILED

    # when status in "exited"
    container_mock.status = "exited"
    expects = [
        (0, ActivationStatus.COMPLETED),
        (1, ActivationStatus.FAILED),
    ]

    for key, value in expects:
        container_mock.attrs = {"State": {"ExitCode": key}}
        activation_status = engine.get_status("container_id")

        assert activation_status.status == value

    # when status is stopped
    container_mock.status = "stopped"
    for key, value in expects:
        container_mock.attrs = {"State": {"ExitCode": key}}
        activation_status = engine.get_status("container_id")

        assert activation_status.status == value


@pytest.mark.django_db
def test_engine_get_status_with_not_found_exception(podman_engine):
    engine = podman_engine

    engine.client.containers.get.side_effect = NotFound("Not found")

    with pytest.raises(
        ContainerNotFoundError, match="Container id 100 not found"
    ):
        engine.get_status("100")


@pytest.mark.django_db
def test_engine_get_status_with_api_error_exception(podman_engine):
    engine = podman_engine

    engine.client.containers.get.side_effect = APIError("unexpected error")

    with pytest.raises(ContainerEngineError):
        engine.get_status("100")


@pytest.mark.django_db
def test_engine_get_status_with_500_not_found(podman_engine):
    engine = podman_engine
    error_msg = (
        "no container with ID "
        "fe244749060b9b546af41eb4256f8e527a031748a64ea3ec93bd821daffc8d89 "
        "found in database: no such container"
    )

    engine.client.containers.get.side_effect = APIError(error_msg)

    with pytest.raises(
        ContainerNotFoundError, match="Container id 100 not found"
    ):
        engine.get_status("100")


@pytest.mark.django_db
def test_engine_cleanup(init_podman_data, podman_engine):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    engine.cleanup("100", log_handler)

    assert models.RulebookProcessLog.objects.last().log.endswith(
        "Container 100 is cleaned up."
    )


@pytest.mark.django_db
def test_engine_cleanup_with_not_found_exception(
    init_podman_data, podman_engine
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    def raise_error(*args, **kwargs):
        raise NotFound("Not found")

    container_mock = mock.Mock()
    engine.client.containers.get.return_value = container_mock
    container_mock.stop.side_effect = raise_error

    engine.cleanup("100", log_handler)

    assert models.RulebookProcessLog.objects.last().log.endswith(
        "Container 100 not found."
    )


@pytest.mark.django_db
def test_engine_cleanup_with_remove_exception(init_podman_data, podman_engine):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    err_msg = "Not found"

    def raise_error(*args, **kwargs):
        raise APIError(err_msg)

    container_mock = mock.Mock()
    engine.client.containers.get.return_value = container_mock
    container_mock.logs.return_value = []
    container_mock.remove.side_effect = raise_error

    with pytest.raises(ContainerCleanupError, match=err_msg):
        engine.cleanup("100", log_handler)


@pytest.mark.django_db
def test_engine_cleanup_with_get_exception(init_podman_data, podman_engine):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    err_msg = "Not found"

    def raise_error(*args, **kwargs):
        raise APIError(err_msg)

    engine.client.containers.get.side_effect = raise_error

    with pytest.raises(ContainerCleanupError, match=err_msg):
        engine.cleanup("100", log_handler)


@pytest.mark.django_db
def test_engine_update_logs(init_podman_data, podman_engine):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)
    init_log_read_at = init_podman_data.activation_instance.log_read_at
    message = (
        "2023-10-31 15:28:01,318 - ansible_rulebook.engine - INFO - "
        "Calling main in ansible.eda.range"
    )

    container_mock = mock.Mock()
    engine.client.containers.get.return_value = container_mock
    container_mock.status = "running"
    container_mock.logs.return_value = [
        (
            "2023-10-31T11:28:00-04:00 2023-10-31 15:28:00,905 - "
            "ansible_rulebook.engine - INFO - load source\n".encode("utf-8")
        ),
        (
            "2023-10-31T11:28:01-04:00 2023-10-31 15:28:01,142 - "
            "ansible_rulebook.engine - INFO - load source filters\n".encode(
                "utf-8"
            )
        ),
        (
            "2023-10-31T11:28:01-04:00 2023-10-31 15:28:01,142 - "
            "ansible_rulebook.engine - INFO - "
            "loading eda.builtin.insert_meta_info\n".encode("utf-8")
        ),
        f"2023-10-31T11:28:01-04:00 {message}".encode("utf-8"),
    ]

    engine.update_logs("100", log_handler)

    assert models.RulebookProcessLog.objects.count() == len(
        container_mock.logs.return_value
    )
    assert models.RulebookProcessLog.objects.last().log == f"{message}"

    init_podman_data.activation_instance.refresh_from_db()
    assert init_podman_data.activation_instance.log_read_at > init_log_read_at


@pytest.mark.django_db
def test_engine_update_logs_with_container_not_found(
    init_podman_data, podman_engine
):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    engine.client.containers.exists.return_value = None
    engine.update_logs("100", log_handler)

    assert models.RulebookProcessLog.objects.last().log.endswith(
        "Container 100 not found."
    )


@pytest.mark.django_db
def test_engine_update_logs_with_exception(init_podman_data, podman_engine):
    engine = podman_engine
    log_handler = DBLogger(init_podman_data.activation_instance.id)

    def raise_error(*args, **kwargs):
        raise APIError("Not found")

    engine.client.containers.exists.side_effect = raise_error

    with pytest.raises(ContainerUpdateLogsError, match="Not found"):
        engine.update_logs("100", log_handler)
