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

from .activation import Activation, RulebookProcess, RulebookProcessLog
from .auth import Permission, Role
from .credential import Credential
from .decision_environment import DecisionEnvironment
from .event_stream import EventStream
from .inventory import Inventory
from .job import (
    ActivationInstanceJobInstance,
    Job,
    JobInstance,
    JobInstanceEvent,
    JobInstanceHost,
)
from .organization import Organization
from .project import ExtraVar, Project
from .queue import ActivationRequestQueue
from .rulebook import (
    AuditAction,
    AuditEvent,
    AuditRule,
    Rule,
    Rulebook,
    Ruleset,
)
from .team import Team
from .user import AwxToken, User

__all__ = [
    "ActivationInstanceJobInstance",
    "RulebookProcessLog",
    "RulebookProcess",
    "Activation",
    "AuditAction",
    "AuditEvent",
    "AuditRule",
    "ExtraVar",
    "Inventory",
    "JobInstanceEvent",
    "JobInstanceHost",
    "JobInstance",
    "Job",
    "Project",
    "Permission",
    "Role",
    "Rule",
    "Rulebook",
    "Ruleset",
    "User",
    "AwxToken",
    "Credential",
    "DecisionEnvironment",
    "ActivationRequestQueue",
    "EventStream",
    "Organization",
    "Team",
]

permission_registry.register(
    Activation,
    Team,
    Organization,
    Credential,
    Activation,
    DecisionEnvironment,
    parent_field_name=None,
)
