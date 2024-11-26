import uuid
from typing import Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from pydantic.error_wrappers import ValidationError

from aap_eda.core import enums, models
from aap_eda.core.models.activation import ActivationStatus
from aap_eda.wsapi.consumers import AnsibleRulebookConsumer

# TODO(doston): this test module needs a whole refactor to use already
# existing fixtures over from API conftest.py instead of creating new objects
# keeping it to minimum for now to pass all failing tests

TIMEOUT = 5

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

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

AAP_INPUTS = {
    "host": "https://eda_controller_url",
    "username": "adam",
    "password": "secret",
    "ssl_verify": "no",
    "oauth_token": "",
}


@pytest.fixture
@pytest.mark.django_db(transaction=True)
async def test_handle_workers_without_credentials(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_with_extra_var = await _prepare_db_data(
        default_organization
    )
    rulebook_process_without_extra_var = (
        await _prepare_activation_instance_without_extra_var()
    )
    rulebook_process_no_token = await _prepare_activation_instance_no_token()

    payload = {
        "type": "Worker",
        "activation_id": rulebook_process_with_extra_var,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "ExtraVars",
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type
        if type == "ControllerInfo":
            assert response["token"] == "XXX"

    payload = {
        "type": "Worker",
        "activation_id": rulebook_process_without_extra_var,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type
        if type == "ControllerInfo":
            assert response["token"] == "XXX"

    payload = {
        "type": "Worker",
        "activation_id": rulebook_process_no_token,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "Rulebook",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type


@pytest.mark.django_db(transaction=True)
async def test_handle_workers_with_eda_system_vault_credential(
    ws_communicator: WebsocketCommunicator,
    preseed_credential_types,
    default_organization: models.Organization,
):
    rulebook_process_id = (
        await _prepare_activation_instance_with_eda_system_vault_credential(
            default_organization,
        )
    )

    payload = {
        "type": "Worker",
        "activation_id": rulebook_process_id,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "Rulebook",
        "VaultCollection",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type
        if type == "VaultCollection":
            data = response["data"]
            assert len(data) == 1
            assert data[0]["type"] == "VaultPassword"
            assert data[0]["password"] == "secret"
            assert data[0]["label"] == "adam"


@pytest.mark.django_db(transaction=True)
async def test_handle_workers_with_controller_info(
    ws_communicator: WebsocketCommunicator,
    preseed_credential_types,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_activation_with_controller_info(
        default_organization,
    )

    payload = {
        "type": "Worker",
        "activation_id": rulebook_process_id,
    }
    await ws_communicator.send_json_to(payload)

    for type in [
        "Rulebook",
        "ControllerInfo",
        "EndOfResponse",
    ]:
        response = await ws_communicator.receive_json_from(timeout=TIMEOUT)
        assert response["type"] == type
        if type == "ControllerInfo":
            assert response["url"] == AAP_INPUTS["host"]
            assert response["username"] == AAP_INPUTS["username"]
            assert response["password"] == AAP_INPUTS["password"]
            assert response["ssl_verify"] == AAP_INPUTS["ssl_verify"]
            assert response["token"] == AAP_INPUTS["oauth_token"]


@pytest.mark.django_db(transaction=True)
async def test_handle_workers_with_validation_errors(
    default_organization: models.Organization,
):
    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect(timeout=3)
    assert connected

    rulebook_process_id = await _prepare_db_data(default_organization)

    payload = {
        "type": "Worker",
        "invalid_activation_id": rulebook_process_id,
    }

    with pytest.raises(ValidationError):
        await communicator.send_json_to(payload)
        await communicator.wait()


@pytest.mark.django_db(transaction=True)
async def test_handle_jobs(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)

    assert (await get_job_instance_count()) == 0
    assert (await get_activation_instance_job_instance_count()) == 0

    payload = {
        "type": "Job",
        "job_id": "940730a1-8b6f-45f3-84c9-bde8f04390e0",
        "ansible_rulebook_id": rulebook_process_id,
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
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)
    job_instance = await _prepare_job_instance()

    assert (await get_audit_rule_count()) == 0
    payload1 = create_action_payload(
        DUMMY_UUID,
        rulebook_process_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
    )
    payload2 = create_action_payload(
        DUMMY_UUID2,
        rulebook_process_id,
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
async def test_handle_actions_with_empty_job_uuid(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)
    assert (await get_audit_rule_count()) == 0

    # job uuid is empty string
    payload = create_action_payload(
        DUMMY_UUID,
        rulebook_process_id,
        "",
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
    )
    await ws_communicator.send_json_to(payload)
    await ws_communicator.wait()

    assert (await get_audit_rule_count()) == 1
    assert (await get_audit_action_count()) == 1
    assert (await get_audit_event_count()) == 2


@pytest.mark.django_db(transaction=True)
async def test_handle_actions(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)
    job_instance = await _prepare_job_instance()

    assert (await get_audit_rule_count()) == 0
    payload = create_action_payload(
        DUMMY_UUID,
        rulebook_process_id,
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
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)
    job_instance = await _prepare_job_instance()

    action1 = create_action_payload(
        DUMMY_UUID,
        rulebook_process_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
    )
    action2 = create_action_payload(
        DUMMY_UUID2,
        rulebook_process_id,
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
async def test_handle_heartbeat(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)
    rulebook_process = await get_rulebook_process(rulebook_process_id)
    activation = await get_activation_by_rulebook_process(rulebook_process_id)
    assert activation.ruleset_stats == {}

    stats = [
        {
            "start": rulebook_process.started_at.strftime(DATETIME_FORMAT),
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
            "ruleSetName": "ruleset1",
        },
        {
            "start": rulebook_process.started_at.strftime(DATETIME_FORMAT),
            "end": "2024-08-21T18:39:12.331Z",
            "numberOfRules": 10,
            "numberOfDisabledRules": 0,
            "rulesTriggered": 1,
            "eventsProcessed": 4000,
            "eventsMatched": 1,
            "eventsSuppressed": 3999,
            "permanentStorageSize": 0,
            "asyncResponses": 0,
            "bytesSentOnAsync": 0,
            "sessionId": 1,
            "ruleSetName": "ruleset2",
        },
    ]

    payloads = [
        {
            "type": "SessionStats",
            "activation_id": rulebook_process_id,
            "stats": stat,
            "reported_at": timezone.now().strftime(DATETIME_FORMAT),
        }
        for stat in stats
    ]

    for payload in payloads:
        await ws_communicator.send_json_to(payload)

    await ws_communicator.wait()

    updated_rulebook_process = await get_rulebook_process(rulebook_process_id)
    assert (
        updated_rulebook_process.updated_at.strftime(DATETIME_FORMAT)
    ) == payload["reported_at"]

    activation = await get_activation_by_rulebook_process(rulebook_process_id)
    assert activation.ruleset_stats is not None
    assert list(activation.ruleset_stats.keys()) == [
        stat["ruleSetName"] for stat in stats
    ]


@pytest.mark.django_db(transaction=True)
async def test_handle_heartbeat_running_status(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(
        default_organization,
        ActivationStatus.STARTING,
    )
    rulebook_process = await get_rulebook_process(rulebook_process_id)
    activation = await get_activation_by_rulebook_process(rulebook_process_id)
    assert activation.ruleset_stats == {}

    stats = [
        {
            "start": rulebook_process.started_at.strftime(DATETIME_FORMAT),
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
            "ruleSetName": "ruleset1",
        },
    ]

    payloads = [
        {
            "type": "SessionStats",
            "activation_id": rulebook_process_id,
            "stats": stat,
            "reported_at": timezone.now().strftime(DATETIME_FORMAT),
        }
        for stat in stats
    ]
    with patch(
        "aap_eda.tasks.orchestrator.enqueue_monitor_rulebook_processes"
    ) as mock_orchestrator:
        for payload in payloads:
            await ws_communicator.send_json_to(payload)

        await ws_communicator.wait()
        mock_orchestrator.assert_called_once()


@pytest.mark.django_db(transaction=True)
async def test_multiple_rules_for_one_event(
    ws_communicator: WebsocketCommunicator,
    default_organization: models.Organization,
):
    rulebook_process_id = await _prepare_db_data(default_organization)
    job_instance = await _prepare_job_instance()

    matching_events = _matching_events()

    action1 = create_action_payload(
        str(uuid.uuid4()),
        rulebook_process_id,
        job_instance.uuid,
        str(uuid.uuid4()),
        "2023-03-29T15:00:17.260803Z",
        matching_events,
    )
    action2 = create_action_payload(
        str(uuid.uuid4()),
        rulebook_process_id,
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


job_url_test_data = [
    (
        "run_job_template",
        "55",
        "http://gw/api/controller",
        "http://controller.com/jobs/1/",
        "http://gw/execution/jobs/playbook/55/details/",
    ),
    (
        "run_workflow_template",
        "55",
        "http://gw/api/controller",
        "http://controller.com/jobs/workflow/55/",
        "http://gw/execution/jobs/workflow/55/details/",
    ),
    (
        "run_job_template",
        "55",
        "http://gw/api/controller/",
        "http://controller.com/jobs/1/",
        "http://gw/execution/jobs/playbook/55/details/",
    ),
    (
        "run_workflow_template",
        "55",
        "http://gw/api/controller/",
        "http://controller.com/jobs/workflow/55/",
        "http://gw/execution/jobs/workflow/55/details/",
    ),
    (
        "run_job_template",
        "55",
        "http://controller.com",
        "http://controller.com/jobs/playbook/2/",
        "http://controller.com/#/jobs/playbook/55/details/",
    ),
    (
        "run_workflow_template",
        "55",
        "http://controller.com",
        "http://controller.com/jobs/workflow/2/",
        "http://controller.com/#/jobs/workflow/55/details/",
    ),
    (
        "run_job_template",
        "55",
        "http://controller.com/",
        "http://controller.com/jobs/playbook/2/",
        "http://controller.com/#/jobs/playbook/55/details/",
    ),
    (
        "run_workflow_template",
        "55",
        "http://controller.com/",
        "http://controller.com/jobs/workflow/2/",
        "http://controller.com/#/jobs/workflow/55/details/",
    ),
    (
        "run_workflow_template",
        "",
        "http://controller.com",
        "http://controller.com/jobs/workflow/2/",
        "http://controller.com/jobs/workflow/2/",
    ),
]


@pytest.mark.parametrize(
    "action_type, controller_job_id, api_url, old_url, new_url",
    job_url_test_data,
)
@pytest.mark.django_db(transaction=True)
async def test_controller_job_url(
    ws_communicator: WebsocketCommunicator,
    preseed_credential_types,
    action_type,
    controller_job_id,
    api_url,
    old_url,
    new_url,
    default_organization: models.Organization,
):
    my_aap_inputs = {
        "host": api_url,
        "username": "adam",
        "password": "secret",
        "ssl_verify": "no",
        "oauth_token": "",
    }
    rulebook_process_id = await _prepare_activation_with_controller_info(
        default_organization, my_aap_inputs
    )
    job_instance = await _prepare_job_instance()

    assert (await get_audit_rule_count()) == 0
    payload = create_action_payload(
        DUMMY_UUID,
        rulebook_process_id,
        job_instance.uuid,
        DUMMY_UUID,
        "2023-03-29T15:00:17.260803Z",
        _matching_events(),
        "successful",
        action_type,
        old_url,
        controller_job_id,
    )
    await ws_communicator.send_json_to(payload)
    await ws_communicator.wait()

    assert (await get_audit_action_count()) == 1
    action = await get_audit_action_first()
    assert action.url == new_url


@database_sync_to_async
def get_rulebook_process(instance_id):
    return models.RulebookProcess.objects.get(pk=instance_id)


@database_sync_to_async
def get_activation_by_rulebook_process(instance_id):
    return models.RulebookProcess.objects.get(pk=instance_id).get_parent()


@database_sync_to_async
def get_audit_events():
    return (
        models.AuditEvent.objects.first(),
        models.AuditEvent.objects.last(),
    )


@database_sync_to_async
def get_audit_events_first():
    return models.AuditEvent.objects.first()


@database_sync_to_async
def get_audit_action_first():
    return models.AuditAction.objects.first()


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
def _prepare_activation_instance_with_eda_system_vault_credential(
    default_organization: models.Organization,
):
    project, _ = models.Project.objects.get_or_create(
        name="test-project",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
        organization=default_organization,
    )

    rulebook, _ = models.Rulebook.objects.get_or_create(
        name="test-rulebook",
        rulesets=TEST_RULESETS,
        project=project,
        organization=default_organization,
    )

    decision_environment = models.DecisionEnvironment.objects.create(
        name="de_test_name_1",
        image_url="de_test_image_url",
        description="de_test_description",
        organization=default_organization,
    )

    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    vault_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.VAULT
    )

    credential = models.EdaCredential.objects.create(
        name="eda_credential",
        inputs={"vault_id": "adam", "vault_password": "secret"},
        managed=False,
        credential_type=vault_credential_type,
        organization=default_organization,
    )

    activation, _ = models.Activation.objects.get_or_create(
        name="test-activation",
        restart_policy=enums.RestartPolicy.ALWAYS,
        rulebook=rulebook,
        project=project,
        user=user,
        decision_environment=decision_environment,
        organization=default_organization,
    )
    activation.eda_credentials.add(credential)

    rulebook_process, _ = models.RulebookProcess.objects.get_or_create(
        activation=activation,
        organization=default_organization,
    )

    return rulebook_process.id


@database_sync_to_async
def _prepare_activation_with_controller_info(
    default_organization: models.Organization,
    inputs=AAP_INPUTS,
):
    project, _ = models.Project.objects.get_or_create(
        name="test-project",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
        organization=default_organization,
    )

    rulebook, _ = models.Rulebook.objects.get_or_create(
        name="test-rulebook",
        rulesets=TEST_RULESETS,
        project=project,
        organization=default_organization,
    )

    decision_environment = models.DecisionEnvironment.objects.create(
        name="de_test_name_1",
        image_url="de_test_image_url",
        description="de_test_description",
        organization=default_organization,
    )

    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )

    credential = models.EdaCredential.objects.create(
        name="eda_credential",
        inputs=inputs,
        managed=False,
        credential_type=aap_credential_type,
        organization=default_organization,
    )

    activation, _ = models.Activation.objects.get_or_create(
        name="test-activation",
        restart_policy=enums.RestartPolicy.ALWAYS,
        rulebook=rulebook,
        project=project,
        user=user,
        decision_environment=decision_environment,
        organization=default_organization,
    )
    activation.eda_credentials.add(credential)

    rulebook_process, _ = models.RulebookProcess.objects.get_or_create(
        activation=activation,
        organization=default_organization,
    )

    return rulebook_process.id


@database_sync_to_async
def _prepare_db_data(
    default_organization: models.Organization, status=ActivationStatus.RUNNING
):
    project, _ = models.Project.objects.get_or_create(
        name="test-project",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
        organization=default_organization,
    )

    rulebook, _ = models.Rulebook.objects.get_or_create(
        name="test-rulebook",
        rulesets=TEST_RULESETS,
        project=project,
        organization=default_organization,
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
    decision_environment = models.DecisionEnvironment.objects.create(
        name="de_test_name_1",
        image_url="de_test_image_url",
        description="de_test_description",
        organization=default_organization,
    )

    activation, _ = models.Activation.objects.get_or_create(
        name="test-activation",
        restart_policy=enums.RestartPolicy.ALWAYS,
        extra_var=TEST_EXTRA_VAR,
        rulebook=rulebook,
        project=project,
        user=user,
        decision_environment=decision_environment,
        awx_token=token[0],
        status=status,
        organization=default_organization,
    )

    rulebook_process, _ = models.RulebookProcess.objects.get_or_create(
        activation=activation,
        status=status,
        organization=default_organization,
    )

    return rulebook_process.id


@database_sync_to_async
def _prepare_activation_instance_without_extra_var(
    default_organization: models.Organization,
):
    project = models.Project.objects.create(
        name="test-project-no-extra_var",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
        organization=default_organization,
    )

    rulebook = models.Rulebook.objects.create(
        name="test-rulebook",
        rulesets=TEST_RULESETS,
        project=project,
        organization=default_organization,
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
    decision_environment = models.DecisionEnvironment.objects.create(
        name="de_test_name_2",
        image_url="de_test_image_url",
        description="de_test_description",
        organization=default_organization,
    )

    activation = models.Activation.objects.create(
        name="test-activation-no-extra_var",
        restart_policy=enums.RestartPolicy.ALWAYS,
        rulebook=rulebook,
        project=project,
        user=user,
        decision_environment=decision_environment,
        awx_token=token[0],
        organization=default_organization,
    )

    rulebook_process = models.RulebookProcess.objects.create(
        activation=activation,
        organization=default_organization,
    )

    return rulebook_process.id


@database_sync_to_async
def _prepare_activation_instance_no_token(
    default_organization: models.Organization,
):
    project = models.Project.objects.create(
        name="test-project-no-token",
        url="https://github.com/test/project",
        git_hash="92156b2b76c6adb9afbd5688550a621bcc2e5782,",
        organization=default_organization,
    )

    rulebook = models.Rulebook.objects.create(
        name="test-rulebook",
        rulesets=TEST_RULESETS,
        project=project,
        organization=default_organization,
    )

    user = models.User.objects.create_user(
        username="obiwan.kenobi",
        first_name="ObiWan",
        last_name="Kenobi",
        email="obiwan@jedicouncil.com",
        password="secret",
    )

    decision_environment = models.DecisionEnvironment.objects.create(
        name="de_no_token",
        image_url="de_test_image_url",
        description="de_test_description",
        organization=default_organization,
    )

    activation = models.Activation.objects.create(
        name="test-activation-no-token",
        restart_policy=enums.RestartPolicy.ALWAYS,
        rulebook=rulebook,
        project=project,
        user=user,
        decision_environment=decision_environment,
        organization=default_organization,
    )

    rulebook_process = models.RulebookProcess.objects.create(
        activation=activation,
        organization=default_organization,
    )

    return rulebook_process.id


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
    action_name="run_playbook",
    action_url="https://www.example.com/",
    controller_job_id="55",
):
    return {
        "type": "Action",
        "action": action_name,
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
        "message": "Action run successfully",
        "url": action_url,
        "controller_job_id": controller_job_id,
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
