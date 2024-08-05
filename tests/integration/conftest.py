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

import logging
import uuid
from typing import Any, Dict, List
from unittest import mock
from unittest.mock import MagicMock, create_autospec

import pytest
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from rest_framework.test import APIClient

from aap_eda.core import enums, models
from aap_eda.core.management.commands.create_initial_data import (
    CREDENTIAL_TYPES,
    populate_credential_types,
)
from aap_eda.core.tasking import Queue, get_redis_client
from aap_eda.core.utils.credentials import inputs_to_store
from aap_eda.services.activation.engine.common import ContainerEngine

DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"
DUMMY_URL = "https://www.example.com"


#################################################################
# Users and API Client
#################################################################
@pytest.fixture()
def new_user():
    return models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )


@pytest.fixture
def default_user() -> models.User:
    """Return a default User."""
    return models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )


@pytest.fixture
def super_user():
    """Return a user with is_superuser=True flag."""
    return models.User.objects.create_user(
        username="superuser",
        password="superuser123",
        email="superuser@localhost",
        is_superuser=True,
    )


@pytest.fixture
def admin_info() -> dict:
    return {"username": "test.admin", "password": "test.admin.123"}


@pytest.fixture
def system_user():
    return models.User.objects.create(username="_system")


@pytest.fixture
def admin_user(default_organization, admin_info):
    user = models.User.objects.create_user(
        username=admin_info["username"],
        password=admin_info["password"],
        email="admin@localhost",
    )
    admin_role = RoleDefinition.objects.create(
        name="Test Admin",
        content_type=ContentType.objects.get_for_model(default_organization),
    )
    admin_role.permissions.add(*DABPermission.objects.all())
    admin_role.give_permission(user, default_organization)
    return user


@pytest.fixture
def default_user_awx_token(default_user: models.User):
    return models.AwxToken.objects.create(
        name="admin-awx-token",
        token="maytheforcebewithyou",
        user=default_user,
    )


@pytest.fixture
def admin_awx_token(admin_user):
    return models.AwxToken.objects.create(
        name="admin-awx-token",
        token="maytheforcebewithyou",
        user=admin_user,
    )


@pytest.fixture
def base_client() -> APIClient:
    """Return APIClient instance with minimal required configuration."""
    client = APIClient(default_format="json")
    return client


@pytest.fixture
def user_client(
    base_client: APIClient, default_user: models.User
) -> APIClient:
    """Return a pre-configured instance of an APIClient with default user."""
    base_client.force_authenticate(user=default_user)
    return base_client


@pytest.fixture
def admin_client(base_client: APIClient, admin_user: models.User) -> APIClient:
    """Return a pre-configured instance of an APIClient with admin user."""
    base_client.force_authenticate(user=admin_user)
    return base_client


@pytest.fixture
def superuser_client(
    base_client: APIClient, super_user: models.User
) -> APIClient:
    """Return a pre-configured instance of an APIClient."""
    base_client.force_authenticate(user=super_user)
    return base_client


@pytest.fixture
def check_permission_mock():
    with mock.patch.object(
        models.User,
        "has_obj_perm",
        autospec=True,
        wraps=models.User.has_obj_perm,
    ) as m:
        yield m


#################################################################
# Decision Environments
#################################################################
@pytest.fixture
def default_decision_environment(
    default_organization: models.Organization,
    default_registry_credential: models.EdaCredential,
) -> models.DecisionEnvironment:
    """Return a default DE."""
    return models.DecisionEnvironment.objects.create(
        name="default_decision_environment",
        image_url="quay.io/ansible/ansible-rulebook:latest",
        description="Default DE",
        eda_credential=default_registry_credential,
        organization=default_organization,
    )


#################################################################
# Projects and Rulebooks
#################################################################
@pytest.fixture
def default_project(
    default_gpg_credential: models.EdaCredential,
    default_scm_credential: models.EdaCredential,
    default_organization: models.Organization,
) -> models.Project:
    """Return a default Project."""
    return models.Project.objects.create(
        name="default-project",
        description="Default Project",
        url="https://git.example.com/acme/project-01",
        git_hash="684f62df18ce5f8d5c428e53203b9b975426eed0",
        eda_credential=default_scm_credential,
        signature_validation_credential=default_gpg_credential,
        scm_branch="main",
        proxy="http://user:secret@myproxy.com",
        organization=default_organization,
        import_state=models.Project.ImportState.COMPLETED,
        import_task_id="c8a7a0e3-05e7-4376-831a-6b8af80107bd",
    )


@pytest.fixture
def new_project(
    default_organization: models.Organization,
) -> models.Project:
    """Return a new Project."""
    return models.Project.objects.create(
        name="new-project",
        description="New Project",
        url="https://git.example.com/acme/project-02",
        git_hash="06a71890b48189edc0b7afccf18285ec042ce302",
        organization=default_organization,
        scm_refspec="refspec",
        verify_ssl=False,
        proxy="http://user:$encrypted$@myproxy.com",
        import_state=models.Project.ImportState.FAILED,
        import_task_id="46e289a7-9dcc-4baa-a49a-a6ca756d9b71",
        import_error="Unexpected error. Please contact support.",
    )


@pytest.fixture
def default_rulesets() -> str:
    return """
---
- name: Test sample 001
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
      filters:
        - noop:
  rules:
    - name: r1
      condition: event.i == 1
      action:
        debug:
    - name: r2
      condition: event.i == 2
      action:
        debug:

- name: Test sample 002
  hosts: all
  sources:
    - ansible.eda.range:
        limit: 5
        delay: 1
  rules:
    - name: r3
      condition: event.i == 2
      action:
        debug:
"""


@pytest.fixture
def default_run_job_template_rulesets() -> str:
    return """
---
- name: test
  sources:
    - ansible.eda.range:
        limit: 10
  rules:
    - name: example rule
      condition: event.i == 8
      actions:
        - run_job_template:
            organization: Default
            name: example
"""


@pytest.fixture
def default_rulebook(
    default_project: models.Project, default_rulesets: str
) -> models.Rulebook:
    """Return a default Rulebook"""
    return models.Rulebook.objects.create(
        name="default-rulebook.yml",
        rulesets=default_rulesets,
        description="test rulebook",
        project=default_project,
    )


@pytest.fixture
def default_rulebook_with_run_job_template(
    default_project: models.Project, default_run_job_template_rulesets: str
) -> models.Rulebook:
    """Return a default Rulebook with run_job_template action"""
    return models.Rulebook.objects.create(
        name="default-rulebook.yml",
        rulesets=default_run_job_template_rulesets,
        description="test rulebook",
        project=default_project,
    )


@pytest.fixture
def ruleset_with_job_template() -> str:
    return """
---
- name: test
  sources:
    - ansible.eda.range:
        limit: 10
  rules:
    - name: example rule
      condition: event.i == 8
      actions:
        - run_job_template:
            organization: Default
            name: example
"""


@pytest.fixture
def rulebook_with_job_template(
    default_project: models.Project, ruleset_with_job_template: str
) -> models.Rulebook:
    rulebook = models.Rulebook.objects.create(
        name="job-template.yml",
        description="rulebook with job template",
        rulesets=ruleset_with_job_template,
        project=default_project,
    )
    return rulebook


@pytest.fixture
def source_list() -> List[dict]:
    return [
        {
            "name": "<unnamed>",
            "type": "range",
            "config": {"limit": 5},
            "source": "ansible.eda.range",
        }
    ]


@pytest.fixture
def ruleset_1(
    default_rulebook: models.Rulebook, source_list: List[dict]
) -> models.Ruleset:
    return models.Ruleset.objects.create(
        name="ruleset-1",
        sources=source_list,
        rulebook=default_rulebook,
    )


@pytest.fixture
def ruleset_2(
    default_rulebook: models.Rulebook, source_list: List[dict]
) -> models.Ruleset:
    return models.Ruleset.objects.create(
        name="ruleset-2",
        sources=source_list,
        rulebook=default_rulebook,
    )


@pytest.fixture
def ruleset_3(
    rulebook_with_job_template: models.Rulebook, source_list: List[dict]
) -> models.Ruleset:
    return models.Ruleset.objects.create(
        name="ruleset-3",
        sources=source_list,
        rulebook=rulebook_with_job_template,
    )


@pytest.fixture
def default_rule(ruleset_1: models.Ruleset) -> models.Rule:
    return models.Rule.objects.create(
        name="say hello",
        action={"run_playbook": {"name": "ansible.eda.hello"}},
        ruleset=ruleset_1,
    )


#################################################################
# Activations and Activation Instances
#################################################################
@pytest.fixture
def default_activation_instance(
    default_activation: models.Activation, default_project: models.Project
) -> models.RulebookProcess:
    """Return a list of Activation Instances"""
    instance = models.RulebookProcess.objects.create(
        name="default-activation-instance",
        activation=default_activation,
        git_hash=default_project.git_hash,
        status=enums.ActivationStatus.COMPLETED,
        status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
            enums.ActivationStatus.COMPLETED
        ],
    )

    models.RulebookProcessQueue.objects.create(
        process=instance,
        queue_name="activation",
    )

    return instance


@pytest.fixture
def default_audit_rule(
    default_activation_instance: models.RulebookProcess,
) -> models.AuditRule:
    return models.AuditRule.objects.create(
        name="default audit rule",
        fired_at="2023-12-14T15:19:02.313122Z",
        rule_uuid=DUMMY_UUID,
        ruleset_uuid=DUMMY_UUID,
        ruleset_name="test-audit-ruleset-name-1",
        activation_instance=default_activation_instance,
    )


@pytest.fixture
def audit_rule_1(
    default_activation_instances: List[models.RulebookProcess],
) -> models.AuditRule:
    return models.AuditRule.objects.create(
        name="rule with 1 action",
        fired_at="2023-12-14T15:19:02.313122Z",
        rule_uuid=DUMMY_UUID,
        ruleset_uuid=DUMMY_UUID,
        ruleset_name="test-audit-ruleset-name-1",
        activation_instance=default_activation_instances[0],
    )


@pytest.fixture
def audit_rule_2(
    new_activation_instance: models.RulebookProcess,
) -> models.AuditRule:
    return models.AuditRule.objects.create(
        name="rule with 2 actions/events",
        fired_at="2023-12-14T15:19:02.323704Z",
        rule_uuid=DUMMY_UUID,
        ruleset_uuid=DUMMY_UUID,
        ruleset_name="test-audit-ruleset-name-2",
        activation_instance=new_activation_instance,
    )


@pytest.fixture
def audit_action_1(audit_rule_1: models.AuditRule) -> models.AuditAction:
    return models.AuditAction.objects.create(
        id=str(uuid.uuid4()),
        name="debug",
        audit_rule=audit_rule_1,
        status="successful",
        rule_fired_at="2023-12-14T15:19:02.313122Z",
        fired_at="2023-12-14T15:19:02.319506Z",
    )


@pytest.fixture
def audit_action_2(audit_rule_2: models.AuditRule) -> models.AuditAction:
    return models.AuditAction.objects.create(
        id=str(uuid.uuid4()),
        name="debug",
        audit_rule=audit_rule_2,
        status="successful",
        rule_fired_at="2023-12-14T15:19:02.323704Z",
        fired_at="2023-12-14T15:19:02.326503Z",
    )


@pytest.fixture
def audit_action_3(audit_rule_2: models.AuditRule) -> models.AuditAction:
    return models.AuditAction.objects.create(
        id=str(uuid.uuid4()),
        name="print_event",
        audit_rule=audit_rule_2,
        status="successful",
        rule_fired_at="2023-12-14T15:19:02.323704Z",
        fired_at="2023-12-14T15:19:02.327547Z",
    )


@pytest.fixture
def audit_event_1(audit_action_1: models.AuditAction) -> models.AuditEvent:
    audit_event = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="my test source",
        source_type="ansible.eda.range",
        rule_fired_at="2023-12-14T15:19:02.313122Z",
        received_at="2023-12-14T15:19:02.289549Z",
        payload={"key": "value"},
    )
    audit_event.audit_actions.add(audit_action_1)
    return audit_event


@pytest.fixture
def audit_event_2(
    audit_action_2: models.AuditAction, audit_action_3: models.AuditAction
) -> models.AuditEvent:
    audit_event = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="my test source",
        source_type="ansible.eda.range",
        rule_fired_at="2023-12-14T15:19:02.323704Z",
        received_at="2023-12-14T15:19:02.313063Z",
        payload={"key": "value"},
    )
    audit_event.audit_actions.add(audit_action_2)
    audit_event.audit_actions.add(audit_action_3)
    return audit_event


@pytest.fixture
def audit_event_3(
    audit_action_2: models.AuditAction, audit_action_3: models.AuditAction
) -> models.AuditEvent:
    audit_event = models.AuditEvent.objects.create(
        id=str(uuid.uuid4()),
        source_name="my test source",
        source_type="ansible.eda.range",
        rule_fired_at="2023-12-14T15:19:02.323704Z",
        received_at="2023-12-14T15:19:02.321472Z",
        payload={"key": "value"},
    )
    audit_event.audit_actions.add(audit_action_2)
    audit_event.audit_actions.add(audit_action_3)
    return audit_event


@pytest.fixture
def default_extra_var_data() -> str:
    """Return a default extra var data"""
    return """
        ---
        collections:
        - community.general
        - benthomasson.eda
        """.strip()


@pytest.fixture
def vault_extra_var_data() -> str:
    return """
        limit: !vault |
                $ANSIBLE_VAULT;1.1;AES256
                32323466393537363831636134336565656265336564633366396632616431376363353231396562
                6334646433623764383863656365386363616136633138390a656331383939323930383061363262
                62376665646431376464653831633634356432323531613661346339643032356366613564386333
                6433633539353862620a343931393734343437613666343039643764333162303436306434663737
                3633
        """.strip()


@pytest.fixture
def activation_payload(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    admin_user: models.User,
) -> dict:
    return {
        "name": "test-activation",
        "description": "Test Activation",
        "is_enabled": True,
        "decision_environment_id": default_decision_environment.id,
        "project_id": default_project.id,
        "rulebook_id": default_rulebook.id,
        "extra_var": default_extra_var_data,
        "organization": default_organization.id,
        "user_id": admin_user.id,
        "restart_policy": enums.RestartPolicy.ON_FAILURE,
        "log_level": enums.RulebookProcessLogLevel.DEBUG,
    }


@pytest.fixture
def activation_payload_blank_text(activation_payload: dict) -> dict:
    activation_payload["description"] = ""
    activation_payload["extra_var"] = ""
    activation_payload["k8s_service_name"] = ""
    return activation_payload


@pytest.fixture
def default_activation(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
    default_vault_credential: models.EdaCredential,
) -> models.Activation:
    """Return a default Activation"""
    activation = models.Activation.objects.create(
        name="default-activation",
        description="Default Activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )
    activation.eda_credentials.add(default_vault_credential)
    return activation


@pytest.fixture
def new_activation(
    default_decision_environment: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var_data: str,
    default_organization: models.Organization,
    default_user: models.User,
) -> models.Activation:
    """Return a new Activation"""
    return models.Activation.objects.create(
        name="new-activation",
        description="New Activation",
        decision_environment=default_decision_environment,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var_data,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )


@pytest.fixture
def default_activation_instances(
    default_activation: models.Activation, default_project: models.Project
) -> models.RulebookProcess:
    """Return a list of Activation Instances"""
    instances = models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="default-activation-instance-1",
                activation=default_activation,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.COMPLETED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.COMPLETED
                ],
            ),
            models.RulebookProcess(
                name="default-activation-instance-2",
                activation=default_activation,
                git_hash=default_project.git_hash,
                status=enums.ActivationStatus.FAILED,
                status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
                    enums.ActivationStatus.FAILED
                ],
            ),
        ]
    )

    for instance in instances:
        models.RulebookProcessQueue.objects.create(
            process=instance,
            queue_name="activation",
        )

    return instances


@pytest.fixture
def new_activation_instance(
    new_activation: models.Activation, default_project: models.Project
) -> models.RulebookProcess:
    """Return an Activation Instance for new_activation fixture"""
    return models.RulebookProcess.objects.create(
        name=new_activation.name,
        activation=new_activation,
        git_hash=default_project.git_hash,
        status=enums.ActivationStatus.COMPLETED,
        status_message=enums.ACTIVATION_STATUS_MESSAGE_MAP[
            enums.ActivationStatus.COMPLETED
        ],
    )


@pytest.fixture
def default_activation_instance_logs(
    default_activation_instances: List[models.RulebookProcess],
) -> List[models.RulebookProcessLog]:
    """Return a list of Activation Instance logs"""
    return models.RulebookProcessLog.objects.bulk_create(
        [
            models.RulebookProcessLog(
                log="activation-instance-log-1",
                activation_instance=default_activation_instances[0],
            ),
            models.RulebookProcessLog(
                log="activation-instance-log-2",
                activation_instance=default_activation_instances[0],
            ),
        ]
    )


#################################################################
# Credentials and Credential Types
#################################################################
INPUTS = {
    "fields": [
        {"id": "username", "label": "Username", "type": "string"},
        {
            "id": "password",
            "label": "Password",
            "type": "string",
            "secret": True,
        },
    ]
}
INJECTORS = {"extra_vars": {"password": "{{ password }}"}}

DUMMY_GPG_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGYxK8IBEACzO/jIqIvEPsIE4xUCRC2WKiyzlD2rEmS/MYg9TMBYTVISrkGF
WfcQE0hPYU5qFeBzsr3qa/AfQobK+sv545QblAbNLINRdoaWnDMwVO+gLeVhrhbv
V2c7kwBe6ahQNy7cK/fh0OilNOwTC9V+HyHO/ZpUm5dniny+R4ScNiVtkegfg7mh
dDiFgAKOLgxElPUJiD/crnIqAWn2OAAqKb1LDGFOdHMJCwI1KH6XRjtmGxy5XX22
NC8zsE0TXfx4Oa8I7cxumZdh9Kw2wWxitSbpQnCT+8LapCwz36BjOjuEVw1c9AxN
UbFuVks1XhBG08SBnkFkAYD5ogTx2hs12PhWCIB2XneHBR7LmgaZzJiYtYoeehQ2
j6JPtIjdPEFgoVxYmSe74+VD/hIYg70Z0tpOpbB/xfvyvVZII/G2hha4l7YCCbN8
a14mN7HLTkaBx2NG7UtcZ5V1ahHznvtSVVqzkJQQqyJyD0sr8oivU3Aq0Cf8pqwL
PIg0Z2h7xCZ0pfxceMB4xFxJGosV+oq25QpasrbDWBhhQw91XpYnRvATYWn3ucU/
20Mn8ZeJOLQxGZLhOfV8rrzGan1czIURlsfnrCC81md3Q3mQTBVhrhTqXrrp7a1f
8ca6xL4d0yAntDudCPEpAOvYYbLsEwqRNNLu1/4uYgCDPsfXNGcTX8Ld9QARAQAB
tCN1c2VyQGFuc2libGUuY29tIDx1c2VyQGFuc2libGUuY29tPokCVAQTAQgAPhYh
BApWMhVpMJ19gBJOItYYZlMrZT/sBQJmMSvCAhsDBQkDwmcABQsJCAcCBhUKCQgL
AgQWAgMBAh4BAheAAAoJENYYZlMrZT/s56wP/1lvAntBZSCMZmTQ3AvpoIyGr2Hc
XwjUlDajYI9A/CdJuOTx/FEZCsfy64K3QCyE9fshozIjiLyuoFb9DPAQ6FKagV0b
Q1sCSSPk+ahaqSUGMQ7Lx8v+Xj0px9qYveeX1s5TisYBFZZPoiZcyhiJxdVZxP0D
kkN+frIfndtzCCEqnYG9XZMDe4LpAmQUExMhp/SvNnuLtEofnIau0ZFyrT+ZG2vm
KAIHyk2yE+N0fn+PzxYJJz77t8htOj/g+4XQZq/U4MhnMdge2raI7fCvh+OixFb0
7QGQpvxlAB0lO5vHf48PPYAgxgjXyiGWG0gpYAcx+t35BJRYlUWOzkjQYDzUvYfs
zGuOVnZbmlX4vtDaU27bMP0575IDtgRYa/p7J1M4BqNUicyelzbeCeSBd6NEyraU
c/deAZFD1MviBzFnbA5yXmxycbiEBmfpypfrsN8k/i4OU+bgZ2GgTLV3TcQcVulh
Z9yJGOc2CcGW9+bCPWOtxzb6ENAv4CmMyL9BmaXKYKXrKKOFnFgjVZU/SqsURoOD
FejSpTMyKeMS174YVm0qh7xw7nX1ph5mibHsS7sCfZCNywQfl91/hpalty7OeXqY
drC6WsDeShPiZlJT47AJgRfEMkZlA6DumlLikkbdCb4Mty2EhaGJ13WCGOzJ3z3k
RMVE39lIPjN2AKyK
=MlEN
-----END PGP PUBLIC KEY BLOCK-----
"""


@pytest.fixture(autouse=True)
def use_debug_setting():
    with override_settings(DEBUG=True):
        yield


@pytest.fixture
def use_shared_resource_setting():
    with override_settings(ALLOW_LOCAL_RESOURCE_MANAGEMENT=False):
        yield


# fixture for a running redis server
@pytest.fixture
def default_credential_type() -> models.CredentialType:
    """Return a default Credential Type."""
    credential_type = models.CredentialType.objects.create(
        name="default_credential_type", inputs=INPUTS, injectors=INJECTORS
    )

    return credential_type


@pytest.fixture
def credential_type() -> models.CredentialType:
    """Return a default Credential Type."""
    credential_type = models.CredentialType.objects.create(
        name="default_credential_type", inputs=INPUTS, injectors=INJECTORS
    )

    return credential_type


@pytest.fixture
def user_credential_type() -> models.CredentialType:
    return models.CredentialType.objects.create(
        name="user_type",
        inputs={
            "fields": [
                {"id": "sasl_username"},
                {"id": "sasl_password"},
            ]
        },
        injectors={
            "extra_vars": {
                "sasl_username": "{{ sasl_username }}",
                "sasl_password": "{{ sasl_password }}",
            }
        },
    )


@pytest.fixture
def default_eda_credential(default_registry_credential: models.EdaCredential):
    return default_registry_credential


@pytest.fixture
def default_registry_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default Container Registry Credential"""
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return models.EdaCredential.objects.create(
        name="default-eda-credential",
        description="Default Registry Credential",
        credential_type=registry_credential_type,
        inputs=inputs_to_store(
            {
                "username": "dummy-user",
                "password": "dummy-password",
                "host": "quay.io",
            }
        ),
        organization=default_organization,
    )


@pytest.fixture
def default_vault_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default Vault Credential"""
    vault_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.VAULT
    )
    return models.EdaCredential.objects.create(
        name="default-vault-credential",
        description="Default Vault Credential",
        credential_type=vault_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def default_scm_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a managed Eda Credential"""
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.SOURCE_CONTROL
    )
    return models.EdaCredential.objects.create(
        name="managed-scm-credential",
        description="Default SCM Credential",
        credential_type=scm_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def new_scm_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a managed Eda Credential"""
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.SOURCE_CONTROL
    )
    return models.EdaCredential.objects.create(
        name="new-scm-credential",
        description="New SCM Credential",
        credential_type=scm_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
    )


@pytest.fixture
def managed_registry_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a managed Eda Credential"""
    scm_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return models.EdaCredential.objects.create(
        name="managed-eda-credential",
        description="Managed Registry Credential",
        credential_type=scm_credential_type,
        inputs=inputs_to_store(
            {"username": "dummy-user", "password": "dummy-password"}
        ),
        organization=default_organization,
        managed=True,
    )


@pytest.fixture
def credential_payload(
    default_organization: models.Organization,
    preseed_credential_types,
) -> Dict[str, Any]:
    """Return the payload for creating a new EdaCredential"""
    registry_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.REGISTRY
    )
    return {
        "name": "test-credential",
        "description": "Test Credential",
        "credential_type": registry_credential_type,
        "inputs": {"username": "dummy-user", "password": "dummy-password"},
        "organization_id": default_organization.id,
    }


@pytest.fixture
def preseed_credential_types(
    default_organization: models.Organization,
) -> list[models.CredentialType]:
    """Preseed Credential Types."""
    return populate_credential_types(CREDENTIAL_TYPES)


@pytest.fixture
def default_gpg_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default GPG Credential"""
    gpg_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.GPG
    )
    return models.EdaCredential.objects.create(
        name="default-gpg-credential",
        description="Default GPG Credential",
        credential_type=gpg_credential_type,
        inputs=inputs_to_store({"gpg_public_key": DUMMY_GPG_KEY}),
        organization=default_organization,
    )


#################################################################
# Organizations and Teams
#################################################################
@pytest.fixture
def default_organization() -> models.Organization:
    "Corresponds to migration add_default_organization"
    return models.Organization.objects.get_or_create(
        name=settings.DEFAULT_ORGANIZATION_NAME,
        description="The default organization",
    )[0]


@pytest.fixture
def new_organization() -> models.Organization:
    "Return a new organization"
    return models.Organization.objects.create(
        name="new-organization",
        description="A new organization",
    )


@pytest.fixture
def default_team(default_organization: models.Organization) -> models.Team:
    """Return a default team in default_organization."""
    return models.Team.objects.create(
        name="Default Team",
        description="This is a default team.",
        organization=default_organization,
    )


@pytest.fixture
def new_team(default_organization: models.Organization) -> models.Team:
    """Return a new team in default_organization."""
    return models.Team.objects.create(
        name="New Team",
        description="This is a new team.",
        organization=default_organization,
    )


#################################################################
# Redis
#################################################################
# fixture for a running redis server
@pytest.fixture
def redis_external(redis_parameters):
    client = get_redis_client(**redis_parameters)
    yield client
    client.flushdb()


@pytest.fixture
def test_queue_name(redis_parameters):
    # Use a separately named copy of the default queue to prevent
    # cross-environment issues.  Using the eda-server default queue results in
    # tasks run by tests to execute within eda-server context, if the
    # eda-server default worker is running, rather than the test context.
    settings.RQ_QUEUES["test-default"] = settings.RQ_QUEUES["default"]

    # The redis parameters provide the DB to use in an effort to avoid
    # stepping on a deployed environment.
    settings.RQ_QUEUES["test-default"]["DB"] = redis_parameters["db"]
    return "test-default"


@pytest.fixture
def default_queue(test_queue_name, redis_external) -> Queue:
    return Queue(test_queue_name, connection=redis_external)


@pytest.fixture
def caplog_factory(caplog):
    def _factory(logger):
        logger.setLevel(logging.INFO)
        logger.handlers += [caplog.handler]
        return caplog

    return _factory


@pytest.fixture
def container_engine_mock() -> MagicMock:
    return create_autospec(ContainerEngine, instance=True)


@pytest.fixture
def default_hmac_credential(
    default_organization: models.Organization,
    preseed_credential_types,
) -> models.EdaCredential:
    """Return a default HMAC Credential"""
    hmac_credential_type = models.CredentialType.objects.get(
        name=enums.WebhookCredentialType.HMAC
    )
    return models.EdaCredential.objects.create(
        name="default-hmac-credential",
        description="Default HMAC Credential",
        credential_type=hmac_credential_type,
        inputs=inputs_to_store(
            {
                "auth_type": "hmac",
                "hmac_algorithm": "sha256",
                "secret": "secret",
                "header_key": "X-Hub-Signature-256",
                "hmac_format": "hex",
                "hmac_signature_prefix": "sha256=",
            }
        ),
        organization=default_organization,
    )


@pytest.fixture
def default_webhooks(
    default_organization: models.Organization,
    default_user: models.User,
    default_hmac_credential: models.EdaCredential,
) -> List[models.Webhook]:
    return models.Webhook.objects.bulk_create(
        [
            models.Webhook(
                uuid=uuid.uuid4(),
                name="test-webhook-1",
                owner=default_user,
                organization=default_organization,
                url=DUMMY_URL,
                eda_credential=default_hmac_credential,
            ),
            models.Webhook(
                uuid=uuid.uuid4(),
                name="test-webhook-2",
                owner=default_user,
                organization=default_organization,
                url=DUMMY_URL,
                eda_credential=default_hmac_credential,
            ),
        ]
    )


@pytest.fixture
def default_webhook(
    default_organization: models.Organization,
    default_user: models.User,
    default_hmac_credential: models.EdaCredential,
) -> models.Webhook:
    return models.Webhook.objects.create(
        uuid=uuid.uuid4(),
        name="test-webhook-1",
        owner=default_user,
        organization=default_organization,
        url=DUMMY_URL,
        eda_credential=default_hmac_credential,
    )
