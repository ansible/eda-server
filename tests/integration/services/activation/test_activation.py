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
    AnsibleRulebookCmdLine,
    ContainerableInvalidError,
    ContainerRequest,
)

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"


@pytest.fixture
def activation_no_instance(
    default_user: models.User,
    default_decision_environment: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
    default_organization: models.Organization,
) -> models.Activation:
    """Return an activation with outassociated RulebookProcess."""
    return models.Activation.objects.create(
        name="test-activation",
        user=default_user,
        decision_environment=default_decision_environment,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
        organization=default_organization,
    )


@pytest.fixture
def activation_no_instance_with_de_credential(
    default_user: models.User,
    default_decision_environment_with_credential: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
    default_organization: models.Organization,
) -> models.Activation:
    """Return an activation with outassociated RulebookProcess."""
    return models.Activation.objects.create(
        name="test-activation",
        user=default_user,
        decision_environment=default_decision_environment_with_credential,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
        organization=default_organization,
    )


@pytest.fixture
def activation(
    default_organization: models.Organization,
    activation_no_instance,
) -> models.Activation:
    """Return an activation with associated RulebookProcess."""
    models.RulebookProcess.objects.create(
        name="activation-instance-1",
        activation=activation_no_instance,
        git_hash=PROJECT_GIT_HASH,
        organization=default_organization,
    )
    return activation_no_instance


@pytest.fixture
def activation_with_de_credential(
    default_organization: models.Organization,
    activation_no_instance_with_de_credential,
) -> models.Activation:
    """Return an activation with associated RulebookProcess."""
    models.RulebookProcess.objects.create(
        name="activation-instance-1",
        activation=activation_no_instance_with_de_credential,
        git_hash=PROJECT_GIT_HASH,
        organization=default_organization,
    )
    return activation_no_instance_with_de_credential


@pytest.mark.django_db
def test_container_request_no_credential(activation):
    """Test container params when no credential exists."""
    request = activation.get_container_request()
    assert request.credential is None


@pytest.mark.django_db
def test_container_request_with_credential(activation_with_de_credential):
    """Test container params when DE credential exists."""
    request = activation_with_de_credential.get_container_request()
    assert request.credential.username == "dummy-user"


@pytest.mark.django_db
def test_get_container_request(activation):
    """Test the construction of a ContainerRequest."""
    request = activation.get_container_request()

    assert isinstance(request, ContainerRequest)
    assert request.name is not None
    assert request.image_url is not None
    assert request.ports is not None
    assert request.env_vars is not None
    assert request.extra_args is not None
    assert request.mem_limit is not None
    assert request.mounts is not None
    assert request.process_parent_id == activation.id
    assert request.rulebook_process_id == activation.latest_instance.id

    cmdline = request.cmdline
    assert (cmdline is not None) and isinstance(
        cmdline, AnsibleRulebookCmdLine
    )
    assert cmdline.id == str(activation.latest_instance.id)
    assert cmdline.ws_url is not None
    assert cmdline.log_level is None
    assert cmdline.ws_ssl_verify is not None
    assert cmdline.ws_token_url is not None
    assert cmdline.ws_access_token is not None
    assert cmdline.ws_refresh_token is not None
    assert cmdline.heartbeat is not None
    assert not cmdline.skip_audit_events
    assert "--skip-audit-events" not in cmdline.get_args()


@pytest.mark.django_db
def test_get_container_request_no_instance(activation_no_instance):
    """Test the construction of a ContainerRequest."""
    with pytest.raises(ContainerableInvalidError):
        activation_no_instance.get_container_request()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("debug", "-vv"),
        ("info", "-v"),
        ("error", None),
    ],
)
@pytest.mark.django_db
def test_log_level_param_activation(activation, value, expected):
    activation.log_level = value
    activation.save(update_fields=["log_level"])
    request = activation.get_container_request()
    assert request.cmdline.log_level == expected
