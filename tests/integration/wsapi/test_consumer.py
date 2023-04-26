from unittest.mock import patch

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from pydantic.error_wrappers import ValidationError

from aap_eda.core import models
from aap_eda.wsapi.consumers import AnsibleRulebookConsumer

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

TEST_INVENTORY = """
---
all:
  hosts:
    localhost:
      ansible_connection: local
      ansible_python_interpreter: /usr/bin/python3
"""

TEST_EXTRA_VAR = """
---
collections:
  - community.general
  - benthomasson.eda  # 1.3.0
"""

TEST_RULESETS = """
---
- name: hello
  hosts: localhost
  gather_facts: false
  tasks:
    - debug:
        msg: hello
"""

DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"


@pytest.mark.django_db(transaction=True)
async def test_ansible_rulebook_consumer():
    communicator = await _prepare_websocket_connection()

    test_payloads = [
        {"handle_workers": {"type": "Worker", "activation_id": "1"}},
        {
            "handle_actions": {
                "type": "Action",
                "action": "run_playbook",
                "action_uuid": DUMMY_UUID,
                "activation_id": 1,
                "run_at": "2023-03-20T18:14:55.036753Z",
                "playbook_name": "playbook",
                "job_id": "uuid_1234",
                "ruleset": "ruleset",
                "ruleset_uuid": DUMMY_UUID,
                "rule": "rule",
                "rule_uuid": DUMMY_UUID,
                "rc": 0,
                "status": "succeeded",
            }
        },
        {
            "handle_jobs": {
                "type": "Job",
                "job_id": "uuid_1234",
                "ansible_rulebook_id": 1,
                "name": "ansible.eda.hello",
                "ruleset": "ruleset",
                "rule": "rule",
                "hosts": "hosts",
                "action": "run_playbook",
                "run_at": "2023-03-20T18:14:55.036753Z",
            }
        },
        {"handle_events": {"type": "AnsibleEvent", "event": {}}},
    ]

    for payload in test_payloads:
        for key, value in payload.items():
            with patch.object(AnsibleRulebookConsumer, key) as mocker:
                await communicator.send_json_to(value)
                response = await communicator.receive_json_from()

                mocker.assert_called_once()

    assert response["type"] == "Hello"

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_handle_workers():
    activation_instance_with_extra_var = await _prepare_db_data()
    activation_instance_without_extra_var = (
        await _prepare_acitvation_instance_without_extra_var()
    )
    communicator = await _prepare_websocket_connection()

    payload = {
        "type": "Worker",
        "activation_id": activation_instance_with_extra_var,
    }
    await communicator.send_json_to(payload)

    for type in [
        "Hello",
        "ExtraVars",
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await communicator.receive_json_from()
        assert response["type"] == type

    payload = {
        "type": "Worker",
        "activation_id": activation_instance_without_extra_var,
    }
    await communicator.send_json_to(payload)

    for type in [
        "Hello",
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await communicator.receive_json_from()
        assert response["type"] == type

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_handle_workers_with_validation_errors():
    activation_instance_id = await _prepare_db_data()
    communicator = await _prepare_websocket_connection()

    payload = {
        "type": "Worker",
        "invalid_activation_id": activation_instance_id,
    }

    with pytest.raises(ValidationError):
        await communicator.send_json_to(payload)
        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_handle_jobs():
    activation_instance_id = await _prepare_db_data()
    communicator = await _prepare_websocket_connection()

    assert (await get_job_instance_count()) == 0
    assert (await get_activation_instance_job_instance_count()) == 0

    payload = {
        "type": "Job",
        "job_id": "940730a1-8b6f-45f3-84c9-bde8f04390e0",
        "ansible_rulebook_id": activation_instance_id,
        "name": "ansible.eda.hello",
        "ruleset": "ruleset",
        "rule": "rule",
        "hosts": "hosts",
        "action": "run_playbook",
    }

    await communicator.send_json_to(payload)
    await communicator.disconnect()

    assert (await get_job_instance_count()) == 1
    assert (await get_activation_instance_job_instance_count()) == 1


@pytest.mark.django_db(transaction=True)
async def test_handle_events():
    communicator = await _prepare_websocket_connection()
    job_instance = await _prepare_job_instance()

    assert (await get_job_instance_event_count()) == 0
    payload = {
        "type": "AnsibleEvent",
        "event": {
            "event": "verbose",
            "job_id": job_instance.uuid,
            "counter": 1,
            "stdout": "the playbook is completed",
        },
    }
    await communicator.send_json_to(payload)
    await communicator.disconnect()

    assert (await get_job_instance_event_count()) == 1


@pytest.mark.django_db(transaction=True)
async def test_handle_actions():
    activation_instance_id = await _prepare_db_data()
    job_instance = await _prepare_job_instance()

    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect()
    assert connected

    assert (await get_audit_rule_count()) == 0
    payload = {
        "type": "Action",
        "action": "run_playbook",
        "action_uuid": DUMMY_UUID,
        "activation_id": activation_instance_id,
        "job_id": job_instance.uuid,
        "ruleset": "ruleset",
        "rule": "rule",
        "ruleset_uuid": DUMMY_UUID,
        "rule_uuid": DUMMY_UUID,
        "run_at": "2023-03-29T15:00:17.260803Z",
        "rule_run_at": "2023-03-29T15:00:17.260803Z",
        "matching_events": {
            "m_1": {
                "meta": {
                    "received_at": "2023-03-29T15:00:17.260803Z",
                    "source": {
                        "name": "my test source",
                        "type": "ansible.eda.range",
                    },
                    "uuid": "523af123-2783-448f-9e2a-d33ad89b04fa",
                },
                "i": 7,
            },
            "m_0": {
                "meta": {
                    "received_at": "2023-03-29T15:00:17.248686Z",
                    "source": {
                        "name": "my test source",
                        "type": "ansible.eda.range",
                    },
                    "uuid": "58d7bbfe-4205-4d25-8cc1-d7e8eea06d21",
                },
                "i": 3,
            },
        },
    }
    await communicator.send_json_to(payload)
    await communicator.disconnect()

    assert (await get_audit_rule_count()) == 1
    assert (await get_audit_action_count()) == 1
    assert (await get_audit_event_count()) == 2

    event1, event2 = await get_audit_events()

    assert str(event1.id) == "523af123-2783-448f-9e2a-d33ad89b04fa"
    assert event1.payload == {"i": 7}
    assert event1.source_name == "my test source"
    assert event1.source_type == "ansible.eda.range"

    assert str(event2.id) == "58d7bbfe-4205-4d25-8cc1-d7e8eea06d21"
    assert event2.payload == {"i": 3}


@pytest.mark.django_db(transaction=True)
async def test_handle_heartbeat():
    communicator = await _prepare_websocket_connection()
    activation_instance_id = await _prepare_db_data()
    connected, _ = await communicator.connect()
    assert connected
    activation_instance = await get_activation_instance(activation_instance_id)

    payload = {
        "type": "SessionStats",
        "activation_id": activation_instance_id,
        "stats": {
            "start": activation_instance.started_at.strftime(DATETIME_FORMAT),
            "end": None,
            "numberOfRules": 1,
            "numberOfDisabledRules": 0,
            "rulesTriggered": 1,
            "eventsProcessed": 2000,
            "eventsMatched": 1,
            "eventsSuppressed": 1999,
            "permanentStorageSize": 0,
            "asyncResponses": 0,
            "bytesSentOnAsync": 0,
            "sessionId": 1,
            "ruleSetName": "ruleset",
        },
        "reported_at": timezone.now().strftime(DATETIME_FORMAT),
    }

    await communicator.send_json_to(payload)
    await communicator.disconnect()
    updated_activation_instance = await get_activation_instance(
        activation_instance_id
    )
    assert (
        updated_activation_instance.updated_at.strftime(DATETIME_FORMAT)
    ) == payload["reported_at"]


@database_sync_to_async
def get_activation_instance(instance_id):
    return models.ActivationInstance.objects.get(pk=instance_id)


@database_sync_to_async
def get_audit_events():
    return (
        models.AuditEvent.objects.first(),
        models.AuditEvent.objects.last(),
    )


@database_sync_to_async
def get_audit_event_count():
    return models.AuditEvent.objects.count()


@database_sync_to_async
def get_audit_action_count():
    return models.AuditAction.objects.count()


@database_sync_to_async
def get_audit_rule_count():
    return models.AuditRule.objects.count()


@database_sync_to_async
def get_job_instance_count():
    return models.JobInstance.objects.count()


@database_sync_to_async
def get_activation_instance_job_instance_count():
    return models.ActivationInstanceJobInstance.objects.count()


@database_sync_to_async
def get_job_instance_event_count():
    return models.JobInstanceEvent.objects.count()


@database_sync_to_async
def _prepare_db_data():
    project, _ = models.Project.objects.get_or_create(
        name="test-project",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
    )

    extra_var, _ = models.ExtraVar.objects.get_or_create(
        name="test-extra_var",
        extra_var=TEST_EXTRA_VAR,
        project=project,
    )

    rulebook, _ = models.Rulebook.objects.get_or_create(
        name="test-rulebook",
        path="rulebooks",
        rulesets=TEST_RULESETS,
        project=project,
    )

    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    token = models.AwxToken.objects.get_or_create(
        user=user, name="token", token="XXX"
    )
    print(token)

    activation, _ = models.Activation.objects.get_or_create(
        name="test-activation",
        restart_policy="always",
        extra_var=extra_var,
        rulebook=rulebook,
        project=project,
        user=user,
    )

    activation_instance, _ = models.ActivationInstance.objects.get_or_create(
        activation=activation,
    )

    ruleset, _ = models.Ruleset.objects.get_or_create(
        name="ruleset",
        sources=[
            {
                "name": "<unnamed>",
                "type": "range",
                "config": {"limit": 5},
                "source": "ansible.eda.range",
            }
        ],
        rulebook=rulebook,
    )

    rule, _ = models.Rule.objects.get_or_create(
        name="rule",
        action={"run_playbook": {"name": "ansible.eda.hello"}},
        ruleset=ruleset,
    )

    return activation_instance.id


@database_sync_to_async
def _prepare_acitvation_instance_without_extra_var():
    project = models.Project.objects.create(
        name="test-project-no-extra_var",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
    )

    rulebook = models.Rulebook.objects.create(
        name="test-rulebook",
        path="rulebooks",
        rulesets=TEST_RULESETS,
        project=project,
    )

    user = models.User.objects.create_user(
        username="luke.skywalker2",
        first_name="Luke",
        last_name="Skywalker2",
        email="luke.skywalker2@example.com",
        password="secret",
    )

    token = models.AwxToken.objects.get_or_create(
        user=user, name="token", token="XXX"
    )

    activation = models.Activation.objects.create(
        name="test-activation-no-extra_var",
        restart_policy="always",
        rulebook=rulebook,
        project=project,
        user=user,
    )

    activation_instance = models.ActivationInstance.objects.create(
        activation=activation,
    )

    return activation_instance.id


@database_sync_to_async
def _prepare_job_instance():
    job_instance, _ = models.JobInstance.objects.get_or_create(
        uuid="940730a1-8b6f-45f3-84c9-bde8f04390e0",
        action="debug",
        name="test",
        ruleset="test-ruleset",
        rule="test-rule",
        hosts="test-hosts",
    )
    return job_instance


async def _prepare_websocket_connection() -> WebsocketCommunicator:
    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect()
    assert connected

    return communicator
