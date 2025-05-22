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

from unittest import mock

import pytest
from kubernetes import client as k8sclient
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus, ProcessParentType
from aap_eda.services.activation.db_log_handler import DBLogger
from aap_eda.services.activation.engine.common import LogHandler
from aap_eda.services.activation.engine.exceptions import (
    ContainerCleanupError,
    ContainerEngineError,
    ContainerEngineInitError,
    ContainerImagePullError,
    ContainerStartError,
)
from aap_eda.services.activation.engine.kubernetes import (
    IMAGE_PULL_BACK_OFF,
    IMAGE_PULL_ERROR,
    INVALID_IMAGE_NAME,
    Engine,
    get_k8s_client,
)

from .utils import get_request


@pytest.fixture
def mock_log_handler():
    return mock.MagicMock(spec=LogHandler)


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
def kubernetes_engine(init_kubernetes_data):
    activation_id = init_kubernetes_data.activation.id
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id=str(activation_id),
            resource_prefix=ProcessParentType.ACTIVATION,
            client=mock.Mock(),
        )

        yield engine


@pytest.mark.parametrize(
    "resource_prefixes",
    [
        {ProcessParentType.ACTIVATION: "activation"},
    ],
)
@pytest.mark.django_db
def test_engine_init(init_kubernetes_data, resource_prefixes):
    activation_id = init_kubernetes_data.activation.id
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        for prefix in resource_prefixes:
            engine = Engine(
                activation_id=str(activation_id),
                resource_prefix=prefix,
                client=mock.Mock(),
            )

            assert engine.namespace == "aap-eda"
            assert (
                engine.secret_name
                == f"{resource_prefixes[prefix]}-secret-{activation_id}"
            )


@pytest.mark.django_db
def test_engine_init_with_exception(init_kubernetes_data):
    activation_id = init_kubernetes_data.activation.id
    with pytest.raises(
        ContainerEngineInitError,
        match=(
            "Namespace file /var/run/secrets/kubernetes.io/serviceaccount"
            "/namespace does not exist."
        ),
    ):
        Engine(
            activation_id=str(activation_id),
            resource_prefix=ProcessParentType.ACTIVATION,
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
def test_engine_start(
    init_kubernetes_data,
    kubernetes_engine,
    default_organization: models.Organization,
):
    engine = kubernetes_engine
    request = get_request(
        init_kubernetes_data,
        "admin",
        default_organization,
        k8s_service_name=init_kubernetes_data.activation.k8s_service_name,
    )
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)

    with mock.patch("aap_eda.services.activation.engine.kubernetes.watch"):
        with mock.patch.object(engine.client, "core_api") as core_api_mock:
            core_api_mock.list_namespaced_service.return_value.items = None
            engine.start(request, log_handler)

    assert engine.job_name == (
        f"activation-job-{init_kubernetes_data.activation.id}-"
        f"{init_kubernetes_data.activation_instance.id}"
    )
    assert engine.pod_name == (
        f"activation-pod-{init_kubernetes_data.activation.id}-"
        f"{init_kubernetes_data.activation_instance.id}"
    )

    assert models.RulebookProcessLog.objects.count() == 6
    assert models.RulebookProcessLog.objects.last().log.endswith(
        f"Job {engine.job_name} is running"
    )


@pytest.mark.django_db
def test_engine_start_with_create_job_exception(
    init_kubernetes_data,
    kubernetes_engine,
    default_organization: models.Organization,
):
    engine = kubernetes_engine
    request = get_request(
        init_kubernetes_data,
        "admin",
        default_organization,
        k8s_service_name=init_kubernetes_data.activation.k8s_service_name,
    )
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)

    def raise_api_error(*args, **kwargs):
        raise ApiException("Job create error")

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.create_namespaced_job.side_effect = raise_api_error
        with mock.patch.object(engine, "cleanup") as cleanup_mock:
            with pytest.raises(ContainerEngineError):
                engine.start(request, log_handler)
                cleanup_mock.assert_called_once()


@pytest.mark.django_db
def test_engine_start_with_pod_status(
    init_kubernetes_data,
    kubernetes_engine,
    default_organization: models.Organization,
):
    engine = kubernetes_engine
    request = get_request(
        init_kubernetes_data,
        "admin",
        default_organization,
        k8s_service_name=init_kubernetes_data.activation.k8s_service_name,
    )
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)

    with mock.patch.object(engine.client, "core_api") as core_api_mock:
        core_api_mock.list_namespaced_service.return_value.items = None
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
    init_kubernetes_data,
    kubernetes_engine,
    image_reasons,
    default_organization: models.Organization,
):
    engine = kubernetes_engine
    request = get_request(
        init_kubernetes_data,
        "admin",
        default_organization,
        k8s_service_name=init_kubernetes_data.activation.k8s_service_name,
    )
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)

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
def test_delete_secret(init_kubernetes_data, kubernetes_engine):
    engine = kubernetes_engine
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)
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
def test_delete_service(init_kubernetes_data, kubernetes_engine):
    engine = kubernetes_engine
    engine.job_name = "activation-job"
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)
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


@mock.patch("aap_eda.services.activation.engine.kubernetes.watch.Watch")
@pytest.mark.django_db
def test_delete_job(mock_watch, init_kubernetes_data, kubernetes_engine):
    engine = kubernetes_engine
    job_name = "eda-job"
    engine.job_name = job_name
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)

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
            f"Job {job_name} is cleaned up."
        )

    event = {"type": "DELETED"}
    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.list_namespaced_job.return_value.items = [job_mock]
        mock_watch.return_value.stream.return_value = [event]
        engine._delete_job(log_handler)

        log_messages = [
            record.log for record in models.RulebookProcessLog.objects.all()
        ]
        assert f"Pod '{job_name}' is deleted." in log_messages


@pytest.mark.django_db
def test_delete_job_with_exception(init_kubernetes_data, kubernetes_engine):
    engine = kubernetes_engine
    job_name = "eda-job"
    engine.job_name = job_name
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)

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
def test_cleanup_orig(init_kubernetes_data, kubernetes_engine):
    engine = kubernetes_engine
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)
    job_name = "eda-job"

    with mock.patch.object(engine, "_delete_secret") as secret_mock:
        with mock.patch.object(engine, "_delete_services") as services_mock:
            with mock.patch.object(engine, "_delete_job") as job_mock:
                engine.cleanup(job_name, log_handler)
                secret_mock.assert_called_once()
                services_mock.assert_called_once()
                job_mock.assert_called_once()


@mock.patch("aap_eda.services.activation.engine.kubernetes.watch.Watch")
@pytest.mark.django_db
def test_pod_cleanup_exception_handling(
    mock_watch, init_kubernetes_data, kubernetes_engine
):
    engine = kubernetes_engine
    log_handler = DBLogger(init_kubernetes_data.activation_instance.id)
    job_name = "test-job"
    engine.job_name = job_name

    job_mock = mock.Mock()
    job_mock.metadata.name = job_name

    with mock.patch.object(engine.client, "batch_api") as batch_api_mock:
        batch_api_mock.list_namespaced_job.return_value.items = [job_mock]

        # Test 404 handling
        mock_watch.return_value.stream.side_effect = ApiException(status=404)
        engine._delete_job(log_handler)

        log_msg = (
            "Pod 'test-job' not found (404), assuming it's already deleted."
        )
        assert models.RulebookProcessLog.objects.last().log.endswith(log_msg)

        # Test generic API error
        mock_watch.return_value.stream.side_effect = ApiException(status=500)
        with pytest.raises(ContainerCleanupError):
            engine._delete_job(log_handler)

        assert models.RulebookProcessLog.objects.last().log.startswith(
            "Error while waiting for deletion:"
        )

        # Verify watcher.stop() always called
        mock_watch.reset_mock()
        mock_watch.return_value.stream.side_effect = ConfigException(
            "Config error"
        )
        with pytest.raises(ConfigException):
            engine._delete_job(log_handler)

        mock_watch.return_value.stop.assert_called_once()
