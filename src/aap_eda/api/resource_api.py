#  Copyright 2024 Red Hat, Inc.
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

from ansible_base.resource_registry.registry import (
    ParentResource,
    ResourceConfig,
    ServiceAPIConfig,
    SharedResource,
)
from ansible_base.resource_registry.shared_types import (
    OrganizationType,
    TeamType,
    UserType,
)

# RBAC models
from ansible_base.rbac.models import RoleDefinition
from ansible_base.resource_registry.shared_types import RoleDefinitionType

from aap_eda.core import models


class APIConfig(ServiceAPIConfig):
    service_type = "eda"


RESOURCE_LIST = (
    ResourceConfig(
        models.User,
        shared_resource=SharedResource(serializer=UserType, is_provider=False),
        name_field="username",
    ),
    ResourceConfig(
        models.Team,
        shared_resource=SharedResource(serializer=TeamType, is_provider=False),
        parent_resources=[
            ParentResource(
                model=models.Organization, field_name="organization"
            )
        ],
    ),
    ResourceConfig(
        models.Organization,
        shared_resource=SharedResource(
            serializer=OrganizationType, is_provider=False
        ),
    ),
    ResourceConfig(
        RoleDefinition,
        shared_resource=SharedResource(
            serializer=RoleDefinitionType, is_provider=False
        ),
    ),
)
