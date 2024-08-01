#  Copyright 2022 Red Hat, Inc.
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

from ansible_base.rbac import permission_registry

from .activation import Activation
from .credential import Credential
from .credential_type import CredentialType
from .decision_environment import DecisionEnvironment
from .eda_credential import EdaCredential
from .event_stream import EventStream
from .job import (
    ActivationInstanceJobInstance,
    Job,
    JobInstance,
    JobInstanceEvent,
    JobInstanceHost,
)
from .organization import Organization
from .project import Project
from .queue import ActivationRequestQueue
from .rulebook import (
    AuditAction,
    AuditEvent,
    AuditRule,
    Rule,
    Rulebook,
    Ruleset,
)
from .rulebook_process import (
    RulebookProcess,
    RulebookProcessLog,
    RulebookProcessQueue,
)
from .team import Team
from .user import AwxToken, User
from .webhook import Webhook

__all__ = [
    "ActivationInstanceJobInstance",
    "RulebookProcessLog",
    "RulebookProcess",
    "RulebookProcessQueue",
    "Activation",
    "AuditAction",
    "AuditEvent",
    "AuditRule",
    "JobInstanceEvent",
    "JobInstanceHost",
    "JobInstance",
    "Job",
    "Project",
    "Rule",
    "Rulebook",
    "Ruleset",
    "User",
    "AwxToken",
    "Credential",
    "CredentialType",
    "EdaCredential",
    "DecisionEnvironment",
    "ActivationRequestQueue",
    "EventStream",
    "Organization",
    "Team",
    "Webhook",
]

permission_registry.register(
    Activation,
    CredentialType,
    EdaCredential,
    DecisionEnvironment,
    Project,
    Organization,
    Team,
    Webhook,
    parent_field_name="organization",
)
permission_registry.register(
    Rulebook,
    parent_field_name="project",
)
permission_registry.register(
    RulebookProcess,
    parent_field_name="activation",
)
permission_registry.register(
    AuditRule, parent_field_name="activation_instance"
)
