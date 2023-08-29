import uuid
from typing import Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from pydantic.error_wrappers import ValidationError

from aap_eda.core import models
from aap_eda.wsapi.consumers import AnsibleRulebookConsumer
from aap_eda.wsapi.exceptions import AwxTokenNotFound

TIMEOUT = 5

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
DUMMY_UUID2 = "8472ff2c-6045-4418-8d4e-46f6cfffffff"


@pytest.mark.django_db(transaction=True)
async def test_ansible_rulebook_consumer(
    ws_communicator: WebsocketCommunicator,
):
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
                await ws_communicator.send_json_to(value)
                response = await ws_communicator.receive_json_from()

                mocker.assert_called_once()

    assert response["type"] == "Hello"


@pytest.mark.django_db(transaction=True)
async def test_handle_workers(ws_communicator: WebsocketCommunicator):
    activation_instance_with_extra_var = await _prepare_db_data()
    activation_instance_without_extra_var = (
        await _prepare_acitvation_instance_without_extra_var()
    )

    payload = {
        "type": "Worker",
        "activation_id": activation_instance_with_extra_var,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "Hello",
        "ExtraVars",
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type

    payload = {
        "type": "Worker",
        "activation_id": activation_instance_without_extra_var,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "Hello",
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type


@pytest.mark.django_db(transaction=True)
async def test_handle_workers_with_validation_errors():
    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect(timeout=3)
    assert connected

    activation_instance_id = await _prepare_db_data()

    payload = {
        "type": "Worker",
        "invalid_activation_id": activation_instance_id,
    }

    with pytest.raises(ValidationError):
        await communicator.send_json_to(payload)
        await communicator.wait()


@pytest.mark.django_db(transaction=True)
async def test_handle_workers_without_awx_token():
    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect(timeout=3)
    assert connected

    activation_instance_id = await _prepare_db_data()

    await sync_to_async(models.AwxToken.objects.all().delete)()

    payload = {
        "type": "Worker",
        "activation_id": activation_instance_id,
    }
    await communicator.send_json_to(payload)
    await communicator.receive_json_from(timeout=TIMEOUT)
    with pytest.raises(AwxTokenNotFound):
        await communicator.receive_json_from(timeout=TIMEOUT)

    loglines = await get_activation_instance_logs(activation_instance_id)
    assert any("AWX token not found" in logline for logline in loglines)


@pytest.mark.django_db(transaction=True)
async def test_handle_jobs(ws_communicator: WebsocketCommunicator):
    activation_instance_id = await _prepare_db_data()

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

    await ws_communicator.send_json_to(payload)
    await ws_communicator.wait()

    assert (await get_job_instance_count()) == 1
    assert (await get_activation_instance_job_instance_count()) == 1


@pytest.mark.django_db(transaction=True)
async def test_handle_events(ws_communicator: WebsocketCommunicator):
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
    await ws_communicator.send_json_to(payload)
    await ws_communicator.wait()

    assert (await get_job_instance_event_count()) == 1


@pytest.mark.django_db(transaction=True)
async def test_handle_actions_multiple_firing(
    ws_communicator: WebsocketCommunicator,
):
    activation_instance_id = await _prepare_db_data()
    job_instance = await _prepare_job_instance()

    assert (await get_audit_rule_count()) == 0
    payload1 = create_action_payload(
        DUMMY_UUID,
        activation_instance_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
    )
    payload2 = create_action_payload(
        DUMMY_UUID2,
        activation_instance_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:27.260803Z",
        _matching_events(),
    )
    await ws_communicator.send_json_to(payload1)
    await ws_communicator.send_json_to(payload2)
    await ws_communicator.wait()

    assert (await get_audit_rule_count()) == 2
    assert (await get_audit_action_count()) == 2
    assert (await get_audit_event_count()) == 4


@pytest.mark.django_db(transaction=True)
async def test_handle_actions(ws_communicator: WebsocketCommunicator):
    activation_instance_id = await _prepare_db_data()
    job_instance = await _prepare_job_instance()

    assert (await get_audit_rule_count()) == 0
    payload = create_action_payload(
        DUMMY_UUID,
        activation_instance_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
    )
    await ws_communicator.send_json_to(payload)
    await ws_communicator.wait()

    assert (await get_audit_rule_count()) == 1
    assert (await get_audit_action_count()) == 1
    assert (await get_audit_event_count()) == 2

    event1, event2 = await get_audit_events()

    event1_data = payload["matching_events"]["m_1"]
    event2_data = payload["matching_events"]["m_0"]
    for event in [event1, event2]:
        if event1_data["meta"]["uuid"] == str(event.id):
            data = event1_data.copy()
        elif event2_data["meta"]["uuid"] == str(event.id):
            data = event2_data.copy()
        else:
            data = None

        assert data is not None
        meta = data.pop("meta")
        assert event.payload == data
        assert event.source_name == meta["source"]["name"]
        assert event.source_type == meta["source"]["type"]


@pytest.mark.django_db(transaction=True)
async def test_rule_status_with_multiple_failed_actions(
    ws_communicator: WebsocketCommunicator,
):
    activation_instance_id = await _prepare_db_data()
    job_instance = await _prepare_job_instance()

    action1 = create_action_payload(
        DUMMY_UUID,
        activation_instance_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
    )
    action2 = create_action_payload(
        DUMMY_UUID2,
        activation_instance_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
        "failed",
    )
    await ws_communicator.send_json_to(action1)
    await ws_communicator.send_json_to(action2)
    await ws_communicator.wait()

    assert (await get_audit_action_count()) == 2
    assert (await get_audit_rule_count()) == 1

    rule = await get_first_audit_rule()
    assert rule.status == "failed"


@pytest.mark.django_db(transaction=True)
async def test_handle_heartbeat(ws_communicator: WebsocketCommunicator):
    activation_instance_id = await _prepare_db_data()
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

    await ws_communicator.send_json_to(payload)
    await ws_communicator.wait()

    updated_activation_instance = await get_activation_instance(
        activation_instance_id
    )
    assert (
        updated_activation_instance.updated_at.strftime(DATETIME_FORMAT)
    ) == payload["reported_at"]


@pytest.mark.django_db(transaction=True)
async def test_multiple_rules_for_one_event(
    ws_communicator: WebsocketCommunicator,
):
    activation_instance_id = await _prepare_db_data()
    job_instance = await _prepare_job_instance()

    matching_events = _matching_events()

    action1 = create_action_payload(
        str(uuid.uuid4()),
        activation_instance_id,
        job_instance.uuid,
        str(uuid.uuid4()),
        "2023-03-29T15:00:17.260803Z",
        matching_events,
    )
    action2 = create_action_payload(
        str(uuid.uuid4()),
        activation_instance_id,
        job_instance.uuid,
        str(uuid.uuid4()),
        "2023-03-29T15:00:17.260803Z",
        matching_events,
    )

    await ws_communicator.send_json_to(action1)
    await ws_communicator.send_json_to(action2)
    await ws_communicator.wait()

    assert (await get_audit_action_count()) == 2
    assert (await get_audit_rule_count()) == 2
    assert (await get_audit_event_count()) == 2

    for event in await get_audit_events():
        assert await get_audit_event_action_count(event) == 2


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
def get_audit_event_action_count(event):
    return event.audit_actions.count()


@database_sync_to_async
def get_first_audit_rule():
    return models.AuditRule.objects.first()


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
def get_activation_instance_logs(instance_id):
    instance = models.ActivationInstance.objects.get(pk=instance_id)
    logs = models.ActivationInstanceLog.objects.filter(
        activation_instance=instance
    ).order_by("line_number")
    return [item.log for item in logs]


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

    models.AwxToken.objects.get_or_create(user=user, name="token", token="XXX")

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

    models.AwxToken.objects.get_or_create(user=user, name="token", token="XXX")

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


@pytest_asyncio.fixture(scope="function")
async def ws_communicator() -> Generator[WebsocketCommunicator, None, None]:
    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect()
    assert connected

    yield communicator
    await communicator.disconnect()


def create_action_payload(
    action_uuid,
    activation_instance_id,
    job_instance_uuid,
    rule_uuid,
    rule_run_at,
    matching_events,
    action_status="successful",
):
    return {
        "type": "Action",
        "action": "run_playbook",
        "action_uuid": action_uuid,
        "activation_id": activation_instance_id,
        "job_id": job_instance_uuid,
        "ruleset": "ruleset",
        "rule": "rule",
        "ruleset_uuid": DUMMY_UUID,
        "rule_uuid": rule_uuid,
        "run_at": "2023-03-29T15:00:17.260803Z",
        "rule_run_at": rule_run_at,
        "matching_events": matching_events,
        "status": action_status,
    }


def _matching_events():
    return {
        "m_1": _create_event(7, str(uuid.uuid4())),
        "m_0": _create_event(3, str(uuid.uuid4())),
    }


def _create_event(data, uuid):
    return {
        "meta": {
            "received_at": "2023-03-29T15:00:17.260803Z",
            "source": {
                "name": "my test source",
                "type": "ansible.eda.range",
            },
            "uuid": uuid,
        },
        "i": data,
    }
