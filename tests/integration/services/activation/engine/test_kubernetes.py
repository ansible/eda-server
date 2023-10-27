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
from unittest import mock

import pytest
from dateutil import parser
from kubernetes import client as k8sclient

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.db_log_handler import DBLogger
from aap_eda.services.activation.engine.common import (
    AnsibleRulebookCmdLine,
    ContainerRequest,
)
from aap_eda.services.activation.engine.exceptions import (
    ContainerCleanupError,
    ContainerEngineInitError,
    ContainerStartError,
)
from aap_eda.services.activation.engine.kubernetes import (
    IMAGE_PULL_BACK_OFF,
    IMAGE_PULL_ERROR,
    INVALID_IMAGE_NAME,
    Engine,
)
from aap_eda.services.activation.exceptions import (
    ActivationImageNotFound,
    ActivationImagePullError,
)


@dataclass
class InitData:
    activation: models.Activation
    activation_instance: models.ActivationInstance


@pytest.fixture()
def init_data():
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
        log_read_at=parser.parse("2023-10-30T19:18:48.362883381Z"),
        activation=activation,
    )

    return InitData(
        activation=activation,
        activation_instance=activation_instance,
    )


def get_ansible_rulebook_cmdline(data: InitData):
    return AnsibleRulebookCmdLine(
        ws_url="ws://localhost:8000/api/eda/ws/ansible-rulebook",
        ws_ssl_verify="no",
        id=data.activation.id,
        log_level="-v",
        heartbeat=5,
    )


def get_request(data: InitData):
    return ContainerRequest(
        name="test-request",
        image_url="quay.io/ansible/ansible-rulebook:main",
        activation_instance_id=data.activation_instance.id,
        activation_id=data.activation.id,
        cmdline=get_ansible_rulebook_cmdline(data),
    )


def get_container_state(phase: str):
    if phase == "Running":
        return k8sclient.V1ContainerState(
            running=k8sclient.V1ContainerStateRunning()
        )

    if phase == "Pending":
        return k8sclient.V1ContainerState(
            waiting=k8sclient.V1ContainerStateWaiting(
                message="waiting_message",
                reason="too many things",
            )
        )

    if phase == "Failed":
        return k8sclient.V1ContainerState(
            terminated=k8sclient.V1ContainerStateTerminated(
                exit_code=1,
                reason="bad things happened",
            )
        )

    if phase == "Succeeded":
        return k8sclient.V1ContainerState(
            terminated=k8sclient.V1ContainerStateTerminated(
                exit_code=0,
            )
        )


def get_stream_event(phase: str):
    pod = k8sclient.V1Pod(
        metadata=k8sclient.V1ObjectMeta(
            name="job_name",
            namespace="aap-eda",
        ),
        status=k8sclient.V1PodStatus(
            container_statuses=[
                k8sclient.V1ContainerStatus(
                    name="container-status",
                    ready=True,
                    image="test_image",
                    image_id="test_image_id",
                    state=get_container_state(phase),
                    restart_count=0,
                )
            ],
            phase=phase,
        ),
    )

    event = {}
    event["object"] = pod
    return [event]


def get_bad_pending_stream_event(reason: str):
    pod = k8sclient.V1Pod(
        metadata=k8sclient.V1ObjectMeta(
            name="job_name",
            namespace="aap-eda",
        ),
        status=k8sclient.V1PodStatus(
            container_statuses=[
                k8sclient.V1ContainerStatus(
                    name="container-status",
                    ready=True,
                    image="test_image",
                    image_id="test_image_id",
                    state=k8sclient.V1ContainerState(
                        waiting=k8sclient.V1ContainerStateWaiting(
                            message="waiting_message",
                            reason=reason,
                        )
                    ),
                    restart_count=0,
                )
            ],
            phase="Pending",
        ),
    )

    event = {}
    event["object"] = pod
    return [event]


def get_pod_statuses(container_status: str):
    if container_status == "running":
        return [
            k8sclient.V1ContainerStatus(
                name="container-status",
                ready=True,
                image="test_image",
                image_id="test_image_id",
                state=k8sclient.V1ContainerState(
                    running=k8sclient.V1ContainerStateRunning()
                ),
                restart_count=0,
            )
        ]
    elif container_status == "terminated":
        return [
            k8sclient.V1ContainerStatus(
                name="container-status",
                ready=True,
                image="test_image",
                image_id="test_image_id",
                state=k8sclient.V1ContainerState(
                    terminated=k8sclient.V1ContainerStateTerminated(
                        exit_code=0,
                    )
                ),
                restart_count=0,
            )
        ]


def get_pod_statuses_with_exit_code(exit_code: int):
    return [
        k8sclient.V1ContainerStatus(
            name="container-status",
            ready=True,
            image="test_image",
            image_id="test_image_id",
            state=k8sclient.V1ContainerState(
                terminated=k8sclient.V1ContainerStateTerminated(
                    exit_code=exit_code,
                )
            ),
            restart_count=0,
        )
    ]


@pytest.fixture
def kubernetes_engine(init_data):
    activation_id = init_data.activation.id
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id=str(activation_id),
            client=mock.Mock(),
        )

        yield engine


@pytest.mark.django_db
def test_engine_init(init_data):
    activation_id = init_data.activation.id
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id=str(activation_id),
            client=mock.Mock(),
        )

        assert engine.namespace == "aap-eda"
        assert engine.secret_name == f"activation-secret-{activation_id}"


@pytest.mark.django_db
def test_engine_init_with_exception(init_data):
    activation_id = init_data.activation.id
    with pytest.raises(
        ContainerEngineInitError,
        match=(
            "Namespace file /var/run/secrets/kubernetes.io/serviceaccount"
            "/namespace does not exist."
        ),
    ):
        Engine(
            activation_id=str(activation_id),
            client=mock.Mock(),
        )


@pytest.mark.django_db
def test_engine_start(init_data, kubernetes_engine):
    engine = kubernetes_engine
    request = get_request(init_data)
    log_handler = DBLogger(init_data.activation_instance.id)

    with mock.patch("aap_eda.services.activation.engine.kubernetes.watch"):
        engine.start(request, log_handler)

    assert engine.job_name == (
        f"activation-job-{init_data.activation.id}-"
        f"{init_data.activation_instance.id}"
    )
    assert engine.pod_name == (
        f"activation-pod-{init_data.activation.id}-"
        f"{init_data.activation_instance.id}"
    )

    assert models.ActivationInstanceLog.objects.count() == 4
    assert (
        models.ActivationInstanceLog.objects.last().log
        == f"Job {engine.job_name} is running"
    )


@pytest.mark.django_db
def test_engine_start_with_pod_status(init_data, kubernetes_engine):
    engine = kubernetes_engine
    request = get_request(init_data)
    log_handler = DBLogger(init_data.activation_instance.id)

    with mock.patch(
        "aap_eda.services.activation.engine.kubernetes.watch"
    ) as watch_mock:
        watcher = mock.Mock()
        watch_mock.Watch.return_value = watcher
        for phase in ["Pending", "Running", "Succeeded"]:
            watcher.stream.return_value = get_stream_event(phase)
            engine.start(request, log_handler)

            assert (
                models.ActivationInstanceLog.objects.last().log
                == f"Job {engine.job_name} is running"
            )

        for phase in ["Failed", "Unknown"]:
            watcher.stream.return_value = get_stream_event(phase)
            with pytest.raises(ContainerStartError):
                with mock.patch.object(engine, "cleanup") as cleanup_mock:
                    engine.start(request, log_handler)
                    cleanup_mock.assert_called_once()


@pytest.mark.parametrize(
    "image_reasons",
    [
        {INVALID_IMAGE_NAME: ActivationImageNotFound},
        {IMAGE_PULL_ERROR: ActivationImagePullError},
        {IMAGE_PULL_BACK_OFF: ActivationImagePullError},
    ],
)
@pytest.mark.django_db
def test_engine_start_with_invalid_image_exception(
    init_data, kubernetes_engine, image_reasons
):
    engine = kubernetes_engine
    request = get_request(init_data)
    log_handler = DBLogger(init_data.activation_instance.id)

    with mock.patch(
        "aap_eda.services.activation.engine.kubernetes.watch"
    ) as watch_mock:
        watcher = mock.Mock()
        watch_mock.Watch.return_value = watcher
        for reason in image_reasons:
            watcher.stream.return_value = get_bad_pending_stream_event(reason)
            with pytest.raises(image_reasons[reason]):
                with mock.patch.object(engine, "cleanup") as cleanup_mock:
                    engine.start(request, log_handler)
                    cleanup_mock.assert_called_once()


@pytest.mark.parametrize(
    "container_statuses",
    [
        {"running": ActivationStatus.RUNNING},
        {"terminated": ActivationStatus.COMPLETED},
    ],
)
@pytest.mark.django_db
def test_get_status(kubernetes_engine, container_statuses):
    engine = kubernetes_engine
    pod_mock = mock.Mock()

    with mock.patch.object(
        engine, "_get_job_pod", mock.Mock(return_value=pod_mock)
    ):
        for key in container_statuses:
            pod_mock.status.container_statuses = get_pod_statuses(key)
            status = engine.get_status("container_id")

            assert status == container_statuses[key]


@pytest.mark.parametrize(
    "exit_codes",
    [
        {0: ActivationStatus.COMPLETED},
        {1: ActivationStatus.FAILED},
        {2: ActivationStatus.FAILED},
        {137: ActivationStatus.FAILED},
        {143: ActivationStatus.COMPLETED},
    ],
)
@pytest.mark.django_db
def test_get_status_with_exit_codes(kubernetes_engine, exit_codes):
    engine = kubernetes_engine
    pod_mock = mock.Mock()

    with mock.patch.object(
        engine, "_get_job_pod", mock.Mock(return_value=pod_mock)
    ):
        for code in exit_codes:
            pod_mock.status.container_statuses = (
                get_pod_statuses_with_exit_code(code)
            )
            status = engine.get_status("container_id")

            assert status == exit_codes[code]


@pytest.mark.django_db
def test_cleanup_secret(init_data, kubernetes_engine):
    engine = kubernetes_engine
    log_handler = DBLogger(init_data.activation_instance.id)
    status_mock = mock.Mock()

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        status_mock.status = "Success"
        core_api_mock.delete_namespaced_secret.return_value = status_mock
        engine._delete_secret(log_handler)

        assert (
            models.ActivationInstanceLog.objects.last().log
            == f"Secret {engine.secret_name} is deleted."
        )

        status_mock.status = "Fail"
        status_mock.reason = "Not found"
        engine._delete_secret(log_handler)

        assert models.ActivationInstanceLog.objects.last().log == (
            f"Failed to delete secret {engine.secret_name}: "
            f"status: {status_mock.status}"
            f"reason: {status_mock.reason}"
        )


@pytest.mark.django_db
def test_cleanup_service(init_data, kubernetes_engine):
    engine = kubernetes_engine
    engine.job_name = "activation-job"
    log_handler = DBLogger(init_data.activation_instance.id)
    service_name = "eda-service"
    service_mock = mock.Mock()
    service_mock.metadata.name = service_name

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_service.return_value.items = [
            service_mock
        ]
        engine._delete_services(log_handler)

        core_api_mock.delete_namespaced_service.assert_called_once()

        assert (
            models.ActivationInstanceLog.objects.last().log
            == f"Service {service_name} is deleted."
        )


@pytest.mark.django_db
def test_cleanup_job(init_data, kubernetes_engine):
    engine = kubernetes_engine
    job_name = "eda-job"
    engine.job_name = job_name
    log_handler = DBLogger(init_data.activation_instance.id)

    job_mock = mock.Mock()
    job_mock.metadata.name = job_name

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.list_namespaced_job.return_value.items = [job_mock]
        engine._delete_job(log_handler)

        batch_api_mock.delete_namespaced_job.assert_called_once()


@pytest.mark.django_db
def test_cleanup_job_with_exception(init_data, kubernetes_engine):
    engine = kubernetes_engine
    job_name = "eda-job"
    engine.job_name = job_name
    log_handler = DBLogger(init_data.activation_instance.id)

    job_mock = mock.Mock()
    job_mock.metadata.name = job_name

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.list_namespaced_job.return_value.items = [job_mock]
        batch_api_mock.delete_namespaced_job.return_value.status = "Failure"

        with pytest.raises(ContainerCleanupError):
            engine._delete_job(log_handler)


@pytest.mark.django_db
def test_cleanup(init_data, kubernetes_engine):
    engine = kubernetes_engine
    log_handler = DBLogger(init_data.activation_instance.id)
    job_name = "eda-job"

    with mock.patch.object(engine, "_delete_secret") as secret_mock:
        with mock.patch.object(engine, "_delete_services") as services_mock:
            with mock.patch.object(engine, "_delete_job") as job_mock:
                engine.cleanup(job_name, log_handler)
                secret_mock.assert_called_once()
                services_mock.assert_called_once()
                job_mock.assert_called_once()

    assert (
        models.ActivationInstanceLog.objects.last().log
        == f"Job {job_name} is cleaned up."
    )


@pytest.mark.django_db
def test_update_logs(init_data, kubernetes_engine):
    engine = kubernetes_engine
    log_handler = DBLogger(init_data.activation_instance.id)
    init_log_read_at = init_data.activation_instance.log_read_at
    job_name = "eda-job"
    pod_mock = mock.Mock()

    with mock.patch.object(
        engine, "_get_job_pod", mock.Mock(return_value=pod_mock)
    ):
        pod_mock.status.container_statuses = get_pod_statuses("running")
        log_mock = mock.Mock()
        message = "2023-10-30 19:18:48,375 INFO Result is kept for 500 seconds"
        with mock.patch.object(engine.client, "core_api") as core_api_mock:
            core_api_mock.read_namespaced_pod_log.return_value = log_mock
            log_mock.splitlines.return_value = [
                (
                    "2023-10-30T19:18:48.362883381Z 2023-10-30 19:18:48,362"
                    " INFO Task started: Monitor project tasks"
                ),
                (
                    "2023-10-30T19:18:48.375144193Z 2023-10-30 19:18:48,374"
                    " INFO Task complete: Monitor project tasks"
                ),
                (
                    "2023-10-30T19:18:48.376026733Z 2023-10-30 19:18:48,375"
                    " INFO default: Job OK (monitor_project_tasks)"
                ),
                f"2023-10-30T19:28:48.376034150Z {message}",
            ]
            engine.update_logs(job_name, log_handler)

    assert models.ActivationInstanceLog.objects.last().log == f"{message}"
    init_data.activation_instance.refresh_from_db()
    assert init_data.activation_instance.log_read_at > init_log_read_at
