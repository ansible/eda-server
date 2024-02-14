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

import django_filters

from aap_eda.core.models import Team


class TeamFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="istartswith",
        label="Filter by team name.",
    )
    organization_id = django_filters.NumberFilter(
        field_name="organization_id",
        lookup_expr="exact",
        label="Filter by organization ID.",
    )
    description = django_filters.CharFilter(
        field_name="description",
        lookup_expr="icontains",
        label="Filter by team description.",
    )

    class Meta:
        model = Team
        fields = ["name", "organization_id", "description"]


class OrganizationTeamFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="istartswith",
        label="Filter by team name.",
    )
    description = django_filters.CharFilter(
        field_name="description",
        lookup_expr="icontains",
        label="Filter by team description.",
    )

    class Meta:
        model = Team
        fields = ["name", "description"]
