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
"""Activation Containerable Interface tests."""

import pytest

from aap_eda.core import models
from aap_eda.services.activation.engine.common import (
    ContainerableInvalidError,
    ContainerRequest,
)

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"


@pytest.fixture
def activation_no_instance(
    default_user: models.User,
    default_decision_environment: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
) -> models.Activation:
    """Return an activation with outassociated RulebookProcess."""
    return models.Activation.objects.create(
        name="test-activation",
        user=default_user,
        decision_environment=default_decision_environment,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
    )


@pytest.fixture
def activation(activation_no_instance) -> models.Activation:
    """Return an activation with associated RulebookProcess."""
    models.RulebookProcess.objects.create(
        name="activation-instance-1",
        activation=activation_no_instance,
        git_hash=PROJECT_GIT_HASH,
    )
    return activation_no_instance


@pytest.mark.django_db
def test_command_line_parameters(activation):
    params = activation.get_command_line_parameters()
    assert params["ws_url"] is not None
    assert params["log_level"] is not None
    assert params["ws_ssl_verify"] is not None
    assert params["ws_token_url"] is not None
    assert params["ws_access_token"] is not None
    assert params["ws_refresh_token"] is not None
    assert params["heartbeat"] is not None
    assert not params["skip_audit_events"]
    assert params["id"] == str(activation.latest_instance.id)


@pytest.mark.django_db
def test_container_parameters(activation):
    params = activation.get_container_parameters()
    assert params["name"] is not None
    assert params["image_url"] is not None
    assert params["ports"] is not None
    assert params["env_vars"] is not None
    assert params["extra_args"] is not None
    assert params["mem_limit"] is not None
    assert params["mounts"] is not None
    assert params["process_parent_id"] == activation.id
    assert params["rulebook_process_id"] == activation.latest_instance.id


@pytest.mark.django_db
def test_container_parameters_no_credential(activation):
    """Test container params when no credential exists."""
    params = activation.get_container_parameters()
    assert params["credential"] is None


@pytest.mark.django_db
def test_get_container_request(activation):
    """Test the construction of a ContainerRequest."""
    request = activation.get_container_request()
    assert isinstance(request, ContainerRequest)
    assert not request.cmdline.skip_audit_events
    assert "--skip-audit-events" not in request.cmdline.get_args()


@pytest.mark.django_db
def test_get_container_request_no_instance(activation_no_instance):
    """Test the construction of a ContainerRequest."""
    with pytest.raises(ContainerableInvalidError):
        activation_no_instance.get_container_request()
