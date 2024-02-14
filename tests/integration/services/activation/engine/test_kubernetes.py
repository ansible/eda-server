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
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.activation.db_log_handler import DBLogger
from aap_eda.services.activation.engine.common import (
    AnsibleRulebookCmdLine,
    ContainerRequest,
    Credential,
)
from aap_eda.services.activation.engine.exceptions import (
    ContainerCleanupError,
    ContainerEngineError,
    ContainerEngineInitError,
    ContainerImagePullError,
    ContainerNotFoundError,
    ContainerStartError,
    ContainerUpdateLogsError,
)
from aap_eda.services.activation.engine.kubernetes import (
    IMAGE_PULL_BACK_OFF,
    IMAGE_PULL_ERROR,
    INVALID_IMAGE_NAME,
    Engine,
    get_k8s_client,
)


@dataclass
class InitData:
    activation: models.Activation
    activation_instance: models.RulebookProcess


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
    activation_instance = models.RulebookProcess.objects.create(
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
        ws_token_url="http://localhost:8000/api/eda/v1/auth/token/refresh",
        ws_access_token="access",
        ws_refresh_token="refresh",
        id=data.activation.id,
        log_level="-v",
        heartbeat=5,
    )


def get_request(data: InitData):
    return ContainerRequest(
        name="test-request",
        image_url="quay.io/ansible/ansible-rulebook:main",
        rulebook_process_id=data.activation_instance.id,
        resource_id=data.activation.id,
        cmdline=get_ansible_rulebook_cmdline(data),
        credential=Credential(username="admin", secret="secret"),
        ports=[("localhost", 8080)],
        mem_limit="8G",
        env_vars={"a": 1},
        extra_args={"b": 2},
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


def get_pod(phase: str):
    return k8sclient.V1Pod(
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


def get_stream_event(phase: str):
    pod = get_pod(phase)

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
    else:
        return [
            k8sclient.V1ContainerStatus(
                name="container-status",
                ready=True,
                image="test_image",
                image_id="test_image_id",
                state=k8sclient.V1ContainerState(
                    waiting=k8sclient.V1ContainerStateWaiting(
                        message="waiting_message",
                        reason="too many things",
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


def test_get_k8s_client():
    with mock.patch("kubernetes.config.load_incluster_config"):
        client = get_k8s_client()

        assert client is not None
        assert client.batch_api is not None
        assert client.core_api is not None
        assert client.network_api is not None


def test_get_k8s_client_exception():
    def raise_config_exception(*args, **kwargs):
        raise ConfigException("Config error")

    with mock.patch(
        "kubernetes.config.load_incluster_config",
        side_effect=raise_config_exception,
    ):
        with pytest.raises(ContainerEngineInitError, match="Config error"):
            get_k8s_client()


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

    assert models.RulebookProcessLog.objects.count() == 5
    assert models.RulebookProcessLog.objects.last().log.endswith(
        f"Job {engine.job_name} is running"
    )


@pytest.mark.django_db
def test_engine_start_with_create_job_exception(init_data, kubernetes_engine):
    engine = kubernetes_engine
    request = get_request(init_data)
    log_handler = DBLogger(init_data.activation_instance.id)

    def raise_api_error(*args, **kwargs):
        raise ApiException("Job create error")

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.create_namespaced_job.side_effect = raise_api_error
        with mock.patch.object(engine, "cleanup") as cleanup_mock:
            with pytest.raises(ContainerEngineError):
                engine.start(request, log_handler)
                cleanup_mock.assert_called_once()


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

            assert models.RulebookProcessLog.objects.last().log.endswith(
                f"Job {engine.job_name} is running"
            )

        watcher.stream.return_value = get_stream_event("Unknown")
        with pytest.raises(ContainerStartError):
            with mock.patch.object(engine, "cleanup") as cleanup_mock:
                engine.start(request, log_handler)
                cleanup_mock.assert_called_once()


@pytest.mark.parametrize(
    "image_reasons",
    [
        {INVALID_IMAGE_NAME: ContainerImagePullError},
        {IMAGE_PULL_ERROR: ContainerImagePullError},
        {IMAGE_PULL_BACK_OFF: ContainerImagePullError},
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
        {"unknown": ActivationStatus.ERROR},
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
            pod_status = engine.get_status("container_id")

            assert pod_status.status == container_statuses[key]


@pytest.mark.parametrize(
    "exit_codes",
    [
        {0: ActivationStatus.COMPLETED},
        {1: ActivationStatus.FAILED},
        {2: ActivationStatus.FAILED},
        {137: ActivationStatus.FAILED},
        {143: ActivationStatus.FAILED},
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
            pod_status = engine.get_status("container_id")

            assert pod_status.status == exit_codes[code]


@pytest.mark.django_db
def test_delete_secret(init_data, kubernetes_engine):
    engine = kubernetes_engine
    log_handler = DBLogger(init_data.activation_instance.id)
    status_mock = mock.Mock()

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        status_mock.status = "Success"
        core_api_mock.delete_namespaced_secret.return_value = status_mock
        engine._delete_secret(log_handler)

        assert models.RulebookProcessLog.objects.last().log.endswith(
            f"Secret {engine.secret_name} is deleted."
        )

        status_mock.status = "Fail"
        status_mock.reason = "Not found"
        engine._delete_secret(log_handler)

        assert models.RulebookProcessLog.objects.last().log.endswith(
            f"Failed to delete secret {engine.secret_name}: "
            f"status: {status_mock.status}"
            f"reason: {status_mock.reason}"
        )

    def raise_api_error(*args, **kwargs):
        raise ApiException("Secret delete error")

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.delete_namespaced_secret.side_effect = raise_api_error

        with pytest.raises(ContainerCleanupError):
            engine._delete_secret(log_handler)


@pytest.mark.django_db
def test_delete_service(init_data, kubernetes_engine):
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

        assert models.RulebookProcessLog.objects.last().log.endswith(
            f"Service {service_name} is deleted."
        )

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_service.return_value.items = [
            service_mock
        ]

        def raise_api_error(*args, **kwargs):
            raise ApiException("Container delete failed")

        core_api_mock.delete_namespaced_service.side_effect = raise_api_error

        with pytest.raises(ContainerCleanupError):
            engine._delete_services(log_handler)


@pytest.mark.django_db
def test_delete_job(init_data, kubernetes_engine):
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

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.list_namespaced_job.return_value.items = None
        engine._delete_job(log_handler)

        assert models.RulebookProcessLog.objects.last().log.endswith(
            f"Job for {job_name} has been removed."
        )


@pytest.mark.django_db
def test_delete_job_with_exception(init_data, kubernetes_engine):
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

    def raise_api_error(*args, **kwargs):
        raise ApiException("Container not found")

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.list_namespaced_job.side_effect = raise_api_error

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

    assert models.RulebookProcessLog.objects.last().log.endswith(
        f"Job {job_name} is cleaned up."
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

            assert models.RulebookProcessLog.objects.last().log == f"{message}"
            init_data.activation_instance.refresh_from_db()
            assert init_data.activation_instance.log_read_at > init_log_read_at

        def raise_api_error(*args, **kwargs):
            raise ApiException("Container not found")

        with mock.patch.object(engine.client, "core_api") as core_api_mock:
            core_api_mock.read_namespaced_pod_log.side_effect = raise_api_error

            with pytest.raises(ContainerUpdateLogsError):
                engine.update_logs(job_name, log_handler)

    with mock.patch.object(
        engine, "_get_job_pod", mock.Mock(return_value=pod_mock)
    ):
        pod_mock.status.container_statuses = get_pod_statuses("unknown")
        log_mock = mock.Mock()
        with mock.patch.object(engine.client, "core_api") as core_api_mock:
            engine.update_logs(job_name, log_handler)
            msg = f"Pod with label {job_name} has unhandled state:"
            assert msg in models.RulebookProcessLog.objects.last().log


@pytest.mark.django_db
def test_get_job_pod(init_data, kubernetes_engine):
    engine = kubernetes_engine
    pods_mock = mock.Mock()
    pod = get_pod("running")

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_pod.return_value = pods_mock
        pods_mock.items = [pod]

        job_pod = engine._get_job_pod("eda-pod")

        assert job_pod is not None
        assert job_pod == pod

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_pod.return_value = pods_mock
        pods_mock.items = None

        with pytest.raises(ContainerNotFoundError):
            engine._get_job_pod("eda-pod")

    def raise_api_error(*args, **kwargs):
        raise ApiException("Container not found")

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_pod.side_effect = raise_api_error

        with pytest.raises(ContainerNotFoundError):
            engine._get_job_pod("eda-pod")


@pytest.mark.django_db
def test_create_service(init_data, kubernetes_engine):
    engine = kubernetes_engine
    engine.job_name = "eda-job"

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_service.return_value.items = None
        engine._create_service(8000)

        core_api_mock.create_namespaced_service.assert_called_once()

    def raise_api_error(*args, **kwargs):
        raise ApiException("Service not found")

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_service.side_effect = raise_api_error

        with pytest.raises(ContainerStartError):
            engine._create_service(8000)


@pytest.mark.django_db
def test_create_secret(init_data, kubernetes_engine):
    engine = kubernetes_engine
    engine.job_name = "eda-job"
    request = get_request(init_data)
    log_handler = DBLogger(init_data.activation_instance.id)

    def raise_api_error(*args, **kwargs):
        raise ApiException("Secret create error")

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.create_namespaced_secret.side_effect = raise_api_error

        with pytest.raises(ContainerStartError):
            engine._create_secret(request, log_handler)
            core_api_mock.delete_namespaced_secret.assert_called_once()
