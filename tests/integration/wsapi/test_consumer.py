from unittest.mock import patch

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from pydantic.error_wrappers import ValidationError

from aap_eda.core import models
from aap_eda.wsapi.consumers import AnsibleRulebookConsumer

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


@pytest.mark.django_db(transaction=True)
async def test_ansible_rulebook_consumer():
    communicator = await _prepare_websocket_connection()

    test_payloads = [
        {"handle_workers": {"type": "Worker", "activation_id": "1"}},
        {
            "handle_actions": {
                "type": "Action",
                "action": "run_playbook",
                "activation_id": 1,
                "playbook_name": "playbook",
                "job_id": "uuid_1234",
                "ruleset": "ruleset",
                "rule": "rule",
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
    activation_instance_id = await _prepare_db_data()
    communicator = await _prepare_websocket_connection()

    payload = {"type": "Worker", "activation_id": activation_instance_id}
    await communicator.send_json_to(payload)

    for type in [
        "Hello",
        "Rulebook",
        "ExtraVars",
        "ControllerUrl",
        "ControllerToken",
        "ControllerSslVerify",
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
        "activation_id": activation_instance_id,
        "playbook_name": "ansible.eda.hello",
        "job_id": job_instance.uuid,
        "ruleset": "ruleset",
        "rule": "rule",
        "rc": 0,
        "run_at": "2023-02-27 18:11:12.566748",
        "status": "succeeded",
    }
    await communicator.send_json_to(payload)
    await communicator.disconnect()

    assert (await get_audit_rule_count()) == 1


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

    models.Inventory.objects.get_or_create(
        name="test-inventory",
        inventory=TEST_INVENTORY,
        inventory_source="collection",
        project_id=project.id,
    )

    extra_var, _ = models.ExtraVar.objects.get_or_create(
        name="test-extra_var",
        extra_var=TEST_EXTRA_VAR,
        project=project,
    )

    rulebook, _ = models.Rulebook.objects.get_or_create(
        name="test-rulebook",
        rulesets=TEST_RULESETS,
        project=project,
    )

    activation, _ = models.Activation.objects.get_or_create(
        name="test-activation",
        restart_policy="always",
        extra_var=extra_var,
        rulebook=rulebook,
        project=project,
    )

    activation_instance, _ = models.ActivationInstance.objects.get_or_create(
        activation=activation,
    )

    ruleset, _ = models.Ruleset.objects.get_or_create(
        name="test-ruleset",
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
