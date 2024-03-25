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
import uuid
from typing import Any, Dict, List
from unittest import mock

import pytest
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core import models
from aap_eda.core.enums import (
    ACTIVATION_STATUS_MESSAGE_MAP,
    ActivationStatus,
    CredentialType,
)

ADMIN_USERNAME = "test.admin"
ADMIN_PASSWORD = "test.admin.123"
DUMMY_UUID = "8472ff2c-6045-4418-8d4e-46f6cffc8557"


@pytest.fixture
def admin_user(default_organization):
    user = models.User.objects.create_user(
        username=ADMIN_USERNAME,
        password=ADMIN_PASSWORD,
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
def client(base_client: APIClient, admin_user: models.User) -> APIClient:
    """Return a pre-configured instance of an APIClient."""
    base_client.force_authenticate(user=admin_user)
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


@pytest.fixture
def default_de(
    default_organization: models.Organization,
    default_credential: models.Credential,
) -> models.DecisionEnvironment:
    """Return a default DE."""
    return models.DecisionEnvironment.objects.create(
        name="default_de",
        image_url="quay.io/ansible/ansible-rulebook:latest",
        description="Default DE",
        credential=default_credential,
        organization=default_organization,
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
def default_user_awx_token(default_user: models.User):
    return models.AwxToken.objects.create(
        name="admin-awx-token",
        token="maytheforcebewithyou",
        user=default_user,
    )


@pytest.fixture
def default_project(
    default_credential: models.Credential,
    default_organization: models.Organization,
) -> models.Project:
    """Return a default Project."""
    return models.Project.objects.create(
        name="default-project",
        description="Default Project",
        url="https://git.example.com/acme/project-01",
        git_hash="684f62df18ce5f8d5c428e53203b9b975426eed0",
        credential=default_credential,
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
        verify_ssl=False,
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
def extra_var_data() -> str:
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
def default_extra_var(
    default_organization: models.Organization,
    extra_var_data: str,
) -> models.ExtraVar:
    """Return a default ExtraVar"""
    return models.ExtraVar.objects.create(
        extra_var=extra_var_data,
        organization=default_organization,
    )


@pytest.fixture
def activation_payload(
    default_de: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var: models.ExtraVar,
    default_organization: models.Organization,
    default_user: models.User,
) -> dict:
    return {
        "name": "test-activation",
        "description": "Test Activation",
        "is_enabled": True,
        "decision_environment_id": default_de.id,
        "project_id": default_project.id,
        "rulebook_id": default_rulebook.id,
        "extra_var_id": default_extra_var.id,
        "organization": default_organization.id,
        "user_id": default_user.id,
        "log_level": "debug",
    }


@pytest.fixture
def default_activation(
    default_de: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var: models.ExtraVar,
    default_organization: models.Organization,
    default_user: models.User,
    default_credential: models.Credential,
) -> models.Activation:
    """Return a default Activation"""
    activation = models.Activation.objects.create(
        name="default-activation",
        description="Default Activation",
        decision_environment=default_de,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )
    activation.credentials.add(default_credential)
    return activation


@pytest.fixture
def new_activation(
    default_de: models.DecisionEnvironment,
    default_project: models.Project,
    default_rulebook: models.Rulebook,
    default_extra_var: models.ExtraVar,
    default_organization: models.Organization,
    default_user: models.User,
) -> models.Activation:
    """Return a new Activation"""
    return models.Activation.objects.create(
        name="new-activation",
        description="New Activation",
        decision_environment=default_de,
        project=default_project,
        rulebook=default_rulebook,
        extra_var=default_extra_var,
        organization=default_organization,
        user=default_user,
        log_level="debug",
    )


@pytest.fixture
def default_activation_instances(
    default_activation: models.Activation, default_project: models.Project
) -> models.RulebookProcess:
    """Return a list of Activation Instances"""
    return models.RulebookProcess.objects.bulk_create(
        [
            models.RulebookProcess(
                name="default-activation-instance-1",
                activation=default_activation,
                git_hash=default_project.git_hash,
                status=ActivationStatus.COMPLETED,
                status_message=ACTIVATION_STATUS_MESSAGE_MAP[
                    ActivationStatus.COMPLETED
                ],
            ),
            models.RulebookProcess(
                name="default-activation-instance-2",
                activation=default_activation,
                git_hash=default_project.git_hash,
                status=ActivationStatus.FAILED,
                status_message=ACTIVATION_STATUS_MESSAGE_MAP[
                    ActivationStatus.FAILED
                ],
            ),
        ]
    )


@pytest.fixture
def new_activation_instance(
    new_activation: models.Activation, default_project: models.Project
) -> models.RulebookProcess:
    """Return an Activation Instance for new_activation fixture"""
    return models.RulebookProcess.objects.create(
        name=new_activation.name,
        activation=new_activation,
        git_hash=default_project.git_hash,
        status=ActivationStatus.COMPLETED,
        status_message=ACTIVATION_STATUS_MESSAGE_MAP[
            ActivationStatus.COMPLETED
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
                line_number=1,
                activation_instance=default_activation_instances[0],
            ),
            models.RulebookProcessLog(
                log="activation-instance-log-2",
                line_number=2,
                activation_instance=default_activation_instances[0],
            ),
        ]
    )


@pytest.fixture
def default_credential(
    default_organization: models.Organization,
) -> models.Credential:
    """Return a default Credential"""
    return models.Credential.objects.create(
        name="default-credential",
        description="Default Credential",
        credential_type=CredentialType.REGISTRY,
        username="dummy-user",
        secret="dummy-password",
        organization=default_organization,
    )


@pytest.fixture
def default_vault_credential(
    default_organization: models.Organization,
) -> models.Credential:
    """Return a default Vault Credential"""
    return models.Credential.objects.create(
        name="default-vault-credential",
        description="Default Vault Credential",
        credential_type=CredentialType.VAULT,
        username="dummy-vault-user",
        secret="dummy-password",
        organization=default_organization,
    )


@pytest.fixture
def default_eda_vault_credential(
    default_organization: models.Organization,
) -> models.Credential:
    """Return a default EDA Vault Credential"""
    return models.Credential.objects.create(
        name="default-eda-vault-credential",
        description="Default EDA Vault Credential",
        vault_identifier=EDA_SERVER_VAULT_LABEL,
        credential_type=CredentialType.VAULT,
        username="dummy-eda-vault-user",
        secret="dummy-password",
        organization=default_organization,
    )


@pytest.fixture
def credential_payload(
    default_organization: models.Organization,
) -> Dict[str, Any]:
    """Return the payload for creating a new Credential"""
    return {
        "name": "test-credential",
        "description": "Test Credential",
        "credential_type": CredentialType.REGISTRY,
        "username": "test-user",
        "secret": "test-password",
        "organization_id": default_organization.id,
    }
