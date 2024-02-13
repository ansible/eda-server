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
"""EventStream Containerable Interface tests."""

import pytest

from aap_eda.core import models

PROJECT_GIT_HASH = "684f62df18ce5f8d5c428e53203b9b975426eed0"


@pytest.fixture
def event_stream(
    default_user: models.User,
    default_decision_environment: models.DecisionEnvironment,
    default_rulebook: models.Rulebook,
) -> models.EventStream:
    """Return an activation with associated RulebookProcess."""
    event_stream = models.EventStream.objects.create(
        name="test-event-stream",
        user=default_user,
        decision_environment=default_decision_environment,
        rulebook=default_rulebook,
        # rulebook_rulesets is populated by the serializer
        rulebook_rulesets=default_rulebook.rulesets,
    )
    process = models.RulebookProcess(
        name="event-stream-instance-1",
        event_stream=event_stream,
        git_hash=PROJECT_GIT_HASH,
    )
    event_stream.latest_instance = process
    return event_stream


@pytest.mark.django_db
def test_command_line_parameters(event_stream):
    params = event_stream.get_command_line_parameters()
    assert params["ws_base_url"] is not None
    assert params["log_level"] is not None
    assert params["ws_ssl_verify"] is not None
    assert params["ws_token_base_url"] is not None
    assert params["ws_access_token"] is not None
    assert params["ws_refresh_token"] is not None
    assert params["heartbeat"] is not None
    assert params["skip_audit_events"]
    assert params["id"] == str(event_stream.latest_instance.id)


@pytest.mark.django_db
def test_container_parameters(event_stream):
    params = event_stream.get_container_parameters()
    assert params["name"] is not None
    assert params["image_url"] is not None
    assert params["ports"] is not None
    assert params["env_vars"] is not None
    assert params["extra_args"] is not None
    assert params["mem_limit"] is not None
    assert params["mounts"] is not None
    assert params["activation_id"] == event_stream.id
    assert params["activation_instance_id"] == event_stream.latest_instance.id


@pytest.mark.django_db
def test_container_parameters_no_credential(event_stream):
    """Test container params when no credential exists."""
    params = event_stream.get_container_parameters()
    assert params["credential"] is None
