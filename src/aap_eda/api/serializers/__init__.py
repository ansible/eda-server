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
    ActivationReadSerializer,
    ActivationSerializer,
    ActivationUpdateSerializer,
)
from .auth import LoginSerializer
from .project import (
    ExtraVarRefSerializer,
    ExtraVarSerializer,
    PlaybookSerializer,
    ProjectCreateRequestSerializer,
    ProjectRefSerializer,
    ProjectSerializer,
)
from .rulebook import (
    RulebookRefSerializer,
    RulebookSerializer,
    RuleOutSerializer,
    RuleSerializer,
    RulesetOutSerializer,
    RulesetSerializer,
)
from .tasks import TaskRefSerializer, TaskSerializer
from .user import UserSerializer

__all__ = (
    # auth
    "LoginSerializer",
    # project
    "ExtraVarSerializer",
    "ExtraVarRefSerializer",
    "PlaybookSerializer",
    "ProjectSerializer",
    "ProjectCreateRequestSerializer",
    "ProjectRefSerializer",
    "RulebookSerializer",
    "RulebookRefSerializer",
    "RulesetOutSerializer",
    "RulesetSerializer",
    "RuleOutSerializer",
    "RuleSerializer",
    # tasks
    "TaskRefSerializer",
    "TaskSerializer",
    # activations
    "ActivationSerializer",
    "ActivationCreateSerializer",
    "ActivationUpdateSerializer",
    "ActivationReadSerializer",
    "ActivationInstanceSerializer",
    "ActivationInstanceLogSerializer",
    # users
    "UserSerializer",
)
