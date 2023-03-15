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
from .credential import CredentialViewSet
from .decision_environment import DecisionEnvironmentViewSet
from .project import ExtraVarViewSet, PlaybookViewSet, ProjectViewSet
from .rulebook import RulebookViewSet, RulesetViewSet, RuleViewSet
from .tasks import TaskViewSet
from .user import CurrentUserView

__all__ = (
    # auth
    "SessionLoginView",
    "SessionLogoutView",
    # project
    "ExtraVarViewSet",
    "PlaybookViewSet",
    "ProjectViewSet",
    "RulebookViewSet",
    "RulesetViewSet",
    "RuleViewSet",
    # tasks
    "TaskViewSet",
    # activations
    "ActivationViewSet",
    "ActivationInstanceViewSet",
    # user
    "CurrentUserView",
    # credential
    "CredentialViewSet",
    # decision_environment
    "DecisionEnvironmentViewSet",
)
