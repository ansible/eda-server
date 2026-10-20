#  Copyright 2026 Red Hat, Inc.
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
from kubernetes.client.rest import ApiException

from aap_eda.services.activation.engine.exceptions import (
    ContainerEngineInitError,
)
from aap_eda.services.activation.engine.kubernetes import (
    K8S_API_RETRIES,
    K8S_API_RETRY_BACKOFF,
    Engine,
    make_job_name,
    resolve_activation_namespace,
    verify_namespace_accessible,
)


@mock.patch.dict(
    "os.environ", {"EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": "eda-jobs"}
)
def test_set_namespace_env_override():
    engine = Engine(
        activation_id="1",
        resource_prefix="activation",
        client=mock.Mock(),
    )
    assert engine.namespace == "eda-jobs"


@mock.patch.dict(
    "os.environ", {"EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": "  eda-jobs  "}
)
def test_set_namespace_env_override_strips_whitespace():
    engine = Engine(
        activation_id="1",
        resource_prefix="activation",
        client=mock.Mock(),
    )
    assert engine.namespace == "eda-jobs"


@mock.patch.dict(
    "os.environ", {"EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": "eda-jobs"}
)
def test_set_namespace_env_override_retries_transient_probe():
    client = mock.Mock()
    client.batch_api.list_namespaced_job.side_effect = [
        ApiException(status=503, reason="Unavailable"),
        None,
    ]

    with mock.patch(
        "aap_eda.services.activation.engine.kubernetes.time.sleep"
    ):
        engine = Engine(
            activation_id="1",
            resource_prefix="activation",
            client=client,
        )

    assert engine.namespace == "eda-jobs"
    assert client.batch_api.list_namespaced_job.call_count == 2


@mock.patch.dict("os.environ", {"EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": ""})
def test_set_namespace_empty_env_falls_back_to_file():
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id="1",
            resource_prefix="activation",
            client=mock.Mock(),
        )
        assert engine.namespace == "aap-eda"


def test_set_namespace_unset_env_falls_back_to_file():
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE"
    }
    with mock.patch.dict("os.environ", env, clear=True):
        with mock.patch(
            "builtins.open",
            mock.mock_open(read_data="my-namespace"),
        ):
            engine = Engine(
                activation_id="1",
                resource_prefix="activation",
                client=mock.Mock(),
            )
            assert engine.namespace == "my-namespace"


@mock.patch.dict(
    "os.environ", {"EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": "   "}
)
def test_set_namespace_whitespace_only_env_falls_back_to_file():
    with mock.patch("builtins.open", mock.mock_open(read_data="aap-eda")):
        engine = Engine(
            activation_id="1",
            resource_prefix="activation",
            client=mock.Mock(),
        )
        assert engine.namespace == "aap-eda"


def test_set_namespace_no_env_no_file_raises():
    with mock.patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ContainerEngineInitError):
            Engine(
                activation_id="1",
                resource_prefix="activation",
                client=mock.Mock(),
            )


# --- verify_namespace_accessible tests ---


def test_verify_namespace_accessible_success():
    """No exception when list_namespaced_job succeeds."""
    batch_api = mock.Mock()
    batch_api.list_namespaced_job.return_value = None
    verify_namespace_accessible(batch_api, "test-ns")
    batch_api.list_namespaced_job.assert_called_once_with(
        namespace="test-ns", limit=1
    )


def test_verify_namespace_accessible_4xx_raises():
    """4xx errors raise ContainerEngineInitError with namespace info."""
    batch_api = mock.Mock()
    batch_api.list_namespaced_job.side_effect = ApiException(
        status=403, reason="Forbidden"
    )
    with pytest.raises(ContainerEngineInitError, match="not accessible"):
        verify_namespace_accessible(batch_api, "forbidden-ns")
    batch_api.list_namespaced_job.assert_called_once()


def test_verify_namespace_accessible_retries_5xx_then_succeeds():
    """Transient server failure during construction need not block init."""
    batch_api = mock.Mock()
    batch_api.list_namespaced_job.side_effect = [
        ApiException(status=503, reason="Unavailable"),
        None,
    ]
    with mock.patch(
        "aap_eda.services.activation.engine.kubernetes.time.sleep"
    ) as sleep:
        verify_namespace_accessible(batch_api, "test-ns")

    assert batch_api.list_namespaced_job.call_count == 2
    sleep.assert_called_once_with(K8S_API_RETRY_BACKOFF)


def test_verify_namespace_accessible_5xx_raises_after_retries():
    """Persistent transient errors still fail closed after bounded retries."""
    batch_api = mock.Mock()
    batch_api.list_namespaced_job.side_effect = ApiException(
        status=500, reason="Internal"
    )
    with mock.patch(
        "aap_eda.services.activation.engine.kubernetes.time.sleep"
    ) as sleep:
        with pytest.raises(ContainerEngineInitError, match="Cannot verify"):
            verify_namespace_accessible(batch_api, "error-ns")

    assert batch_api.list_namespaced_job.call_count == K8S_API_RETRIES
    assert sleep.call_args_list == [
        mock.call(K8S_API_RETRY_BACKOFF * attempt)
        for attempt in range(1, K8S_API_RETRIES)
    ]


def test_verify_namespace_accessible_non_transient_5xx_raises_immediately():
    batch_api = mock.Mock()
    batch_api.list_namespaced_job.side_effect = ApiException(
        status=501, reason="Not Implemented"
    )
    with mock.patch(
        "aap_eda.services.activation.engine.kubernetes.time.sleep"
    ) as sleep:
        with pytest.raises(ContainerEngineInitError, match="Cannot verify"):
            verify_namespace_accessible(batch_api, "error-ns")

    batch_api.list_namespaced_job.assert_called_once()
    sleep.assert_not_called()


# --- resolve_activation_namespace tests ---


@mock.patch.dict(
    "os.environ", {"EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": "override-ns"}
)
def test_resolve_activation_namespace_env_override():
    """Env var returns (namespace, True)."""
    ns, is_override = resolve_activation_namespace()
    assert ns == "override-ns"
    assert is_override is True


def test_resolve_activation_namespace_sa_file():
    """SA file returns (namespace, False) when both overrides are unset."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE",
            "EDA_ACTIVATION_JOB_NAMESPACE",
        }
    }
    with mock.patch.dict("os.environ", env, clear=True):
        with mock.patch("builtins.open", mock.mock_open(read_data="sa-ns")):
            ns, is_override = resolve_activation_namespace()
            assert ns == "sa-ns"
            assert is_override is False


def test_resolve_activation_namespace_no_env_no_file():
    """No env and no file raises ContainerEngineInitError."""
    with mock.patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ContainerEngineInitError, match="Cannot determine"):
            resolve_activation_namespace()


# --- deprecated env var fallback tests ---


@mock.patch.dict(
    "os.environ",
    {"EDA_ACTIVATION_JOB_NAMESPACE": "legacy-ns"},
    clear=True,
)
def test_resolve_deprecated_env_var_fallback():
    """Old env var works as fallback with is_override=True."""
    ns, is_override = resolve_activation_namespace()
    assert ns == "legacy-ns"
    assert is_override is True


@mock.patch.dict(
    "os.environ",
    {
        "EDA_CONTAINER_GROUP_DEFAULT_NAMESPACE": "new-ns",
        "EDA_ACTIVATION_JOB_NAMESPACE": "old-ns",
    },
)
def test_resolve_new_env_var_takes_precedence():
    """New env var takes precedence over old."""
    ns, is_override = resolve_activation_namespace()
    assert ns == "new-ns"
    assert is_override is True


@mock.patch.dict(
    "os.environ",
    {"EDA_ACTIVATION_JOB_NAMESPACE": "legacy-ns"},
    clear=True,
)
def test_set_namespace_deprecated_env_override():
    """Engine uses deprecated env var when new one is not set."""
    engine = Engine(
        activation_id="1",
        resource_prefix="activation",
        client=mock.Mock(),
    )
    assert engine.namespace == "legacy-ns"


# --- make_job_name tests ---


def test_make_job_name():
    assert make_job_name("activation", 42, 7) == "activation-job-42-7"


def test_make_job_name_different_prefix():
    assert make_job_name("event-stream", 1, 2) == "event-stream-job-1-2"


# --- ACTIVATION_TERMINAL_STATUSES tests ---


def test_activation_terminal_statuses_contains_expected():
    """All four terminal statuses are present."""
    from aap_eda.core.enums import (
        ACTIVATION_TERMINAL_STATUSES,
        ActivationStatus,
    )

    expected = {
        ActivationStatus.STOPPED,
        ActivationStatus.COMPLETED,
        ActivationStatus.FAILED,
        ActivationStatus.ERROR,
    }
    assert ACTIVATION_TERMINAL_STATUSES == expected


def test_activation_terminal_statuses_excludes_running():
    from aap_eda.core.enums import (
        ACTIVATION_TERMINAL_STATUSES,
        ActivationStatus,
    )

    assert ActivationStatus.RUNNING not in ACTIVATION_TERMINAL_STATUSES
    assert ActivationStatus.STARTING not in ACTIVATION_TERMINAL_STATUSES
