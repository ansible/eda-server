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

from .activation import (
    ActivationCreateSerializer,
    ActivationInstanceLogSerializer,
    ActivationInstanceSerializer,
    ActivationListSerializer,
    ActivationReadSerializer,
    ActivationSerializer,
    PostActivationSerializer,
)
from .auth import LoginSerializer
from .config import ConfigSerializer
from .credential_type import (
    CredentialTypeCreateSerializer,
    CredentialTypeRefSerializer,
    CredentialTypeSerializer,
)
from .decision_environment import (
    DecisionEnvironmentCreateSerializer,
    DecisionEnvironmentReadSerializer,
    DecisionEnvironmentRefSerializer,
    DecisionEnvironmentSerializer,
)
from .eda_credential import (
    EdaCredentialCreateSerializer,
    EdaCredentialSerializer,
)
from .event_stream import EventStreamInSerializer, EventStreamOutSerializer
from .organization import (
    OrganizationCreateSerializer,
    OrganizationRefSerializer,
    OrganizationSerializer,
)
from .project import (
    ProjectCreateRequestSerializer,
    ProjectReadSerializer,
    ProjectRefSerializer,
    ProjectSerializer,
    ProjectUpdateRequestSerializer,
)
from .rulebook import (
    AuditActionSerializer,
    AuditEventSerializer,
    AuditRuleDetailSerializer,
    AuditRuleListSerializer,
    AuditRuleSerializer,
    RulebookRefSerializer,
    RulebookSerializer,
)
from .source import SourceSerializer
from .team import (
    TeamCreateSerializer,
    TeamDetailSerializer,
    TeamSerializer,
    TeamUpdateSerializer,
)
from .user import (
    AwxTokenCreateSerializer,
    AwxTokenSerializer,
    CurrentUserUpdateSerializer,
    UserCreateUpdateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserSerializer,
)

__all__ = (
    # auth
    "LoginSerializer",
    # project
    "ProjectSerializer",
    "ProjectCreateRequestSerializer",
    "ProjectUpdateRequestSerializer",
    "ProjectRefSerializer",
    "AuditActionSerializer",
    "AuditEventSerializer",
    "AuditRuleSerializer",
    "AuditRuleDetailSerializer",
    "AuditRuleListSerializer",
    "RulebookSerializer",
    "RulebookRefSerializer",
    # activations
    "ActivationSerializer",
    "ActivationListSerializer",
    "ActivationCreateSerializer",
    "ActivationReadSerializer",
    "ActivationInstanceSerializer",
    "ActivationInstanceLogSerializer",
    "PostActivationSerializer",
    # users
    "AwxTokenSerializer",
    "AwxTokenCreateSerializer",
    "CurrentUserUpdateSerializer",
    "UserSerializer",
    "UserListSerializer",
    "UserCreateUpdateSerializer",
    "UserDetailSerializer",
    # config
    "ConfigSerializer",
    # credential type
    "CredentialTypeSerializer",
    "CredentialTypeCreateSerializer",
    "CredentialTypeRefSerializer",
    "EdaCredentialSerializer",
    "EdaCredentialCreateSerializer",
    # decision environment
    "DecisionEnvironmentSerializer",
    # organizations
    "OrganizationSerializer",
    "OrganizationCreateSerializer",
    "OrganizationRefSerializer",
    # sources
    "SourceSerializer",
    # teams
    "TeamSerializer",
    "TeamCreateSerializer",
    "TeamUpdateSerializer",
    "TeamDetailSerializer",
    # event streams
    "EventStreamInSerializer",
    "EventStreamOutSerializer",
)
