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

"""Tests for namespace-aware lifecycle in ActivationManager."""

from unittest.mock import MagicMock, create_autospec, patch

import pytest

from aap_eda.services.activation.activation_manager import ActivationManager
from aap_eda.services.activation.engine.common import ContainerEngine
from aap_eda.services.activation.engine.kubernetes import (
    Engine as KubernetesEngine,
)


class TestInstanceEngine:
    """Tests for _instance_engine context manager."""

    def _make_manager(self, activation, engine):
        return ActivationManager(activation, container_engine=engine)

    def test_swaps_namespace_for_recorded_process(self):
        """When process has a namespace, engine namespace is swapped."""
        engine = MagicMock(spec=KubernetesEngine)
        engine.namespace = "current-ns"

        instance = MagicMock()
        instance.activation_job_namespace = "old-ns"
        instance.id = 1

        activation = MagicMock()
        manager = self._make_manager(activation, engine)

        with manager._instance_engine(instance):
            assert engine.namespace == "old-ns"
        assert engine.namespace == "current-ns"

    def test_restores_namespace_on_exception(self):
        """Engine namespace restored even when block raises."""
        engine = MagicMock(spec=KubernetesEngine)
        engine.namespace = "current-ns"

        instance = MagicMock()
        instance.activation_job_namespace = "old-ns"
        instance.id = 1

        activation = MagicMock()
        manager = self._make_manager(activation, engine)

        def raise_inside_instance_engine():
            with manager._instance_engine(instance):
                assert engine.namespace == "old-ns"
                raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            raise_inside_instance_engine()
        assert engine.namespace == "current-ns"

    @patch(
        "aap_eda.services.activation.activation_manager."
        "get_service_account_namespace",
        return_value="control-plane-ns",
    )
    def test_null_namespace_records_and_uses_legacy_namespace(
        self, get_control_plane_namespace
    ):
        """A legacy process never uses the configured namespace as source."""
        engine = MagicMock(spec=KubernetesEngine)
        engine.namespace = "target-ns"

        instance = MagicMock()
        instance.activation_job_namespace = None
        instance.id = 2

        activation = MagicMock()
        manager = self._make_manager(activation, engine)

        with manager._instance_engine(instance):
            assert engine.namespace == "control-plane-ns"
        assert engine.namespace == "target-ns"
        assert instance.activation_job_namespace == "control-plane-ns"
        instance.save.assert_called_once_with(
            update_fields=["activation_job_namespace"]
        )
        get_control_plane_namespace.assert_called_once_with()

    @patch(
        "aap_eda.services.activation.activation_manager."
        "get_service_account_namespace",
        return_value="control-plane-ns",
    )
    def test_empty_namespace_records_and_uses_legacy_namespace(
        self, get_control_plane_namespace
    ):
        """An empty legacy value is treated the same as a null value."""
        engine = MagicMock(spec=KubernetesEngine)
        engine.namespace = "target-ns"

        instance = MagicMock()
        instance.activation_job_namespace = ""
        instance.id = 3

        activation = MagicMock()
        manager = self._make_manager(activation, engine)

        with manager._instance_engine(instance):
            assert engine.namespace == "control-plane-ns"
        assert engine.namespace == "target-ns"
        assert instance.activation_job_namespace == "control-plane-ns"
        instance.save.assert_called_once_with(
            update_fields=["activation_job_namespace"]
        )
        get_control_plane_namespace.assert_called_once_with()

    def test_non_k8s_engine_yields_without_swap(self):
        """Non-Kubernetes engine yields without any namespace logic."""
        engine = create_autospec(ContainerEngine, instance=True)

        instance = MagicMock()
        instance.activation_job_namespace = "some-ns"

        activation = MagicMock()
        manager = self._make_manager(activation, engine)

        with manager._instance_engine(instance):
            pass
