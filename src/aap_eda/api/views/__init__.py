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

from .activation import ActivationInstanceViewSet, ActivationViewSet
from .auth import SessionLoginView, SessionLogoutView
from .credential_type import CredentialTypeViewSet
from .decision_environment import DecisionEnvironmentViewSet
from .eda_credential import EdaCredentialViewSet
from .event_stream import EventStreamViewSet
from .organization import OrganizationViewSet
from .project import ProjectViewSet
from .rulebook import AuditRuleViewSet, RulebookViewSet
from .team import TeamViewSet
from .user import CurrentUserAwxTokenViewSet, CurrentUserView, UserViewSet

__all__ = (
    # auth
    "SessionLoginView",
    "SessionLogoutView",
    "RoleViewSet",
    # project
    "ProjectViewSet",
    "AuditRuleViewSet",
    "RulebookViewSet",
    # activations
    "ActivationViewSet",
    "ActivationInstanceViewSet",
    # user
    "CurrentUserView",
    "CurrentUserAwxTokenViewSet",
    "UserViewSet",
    # credential
    "CredentialTypeViewSet",
    "EdaCredentialViewSet",
    # decision_environment
    "DecisionEnvironmentViewSet",
    # event_stream
    "EventStreamViewSet",
    # organizations
    "OrganizationViewSet",
    # teams
    "TeamViewSet",
)
