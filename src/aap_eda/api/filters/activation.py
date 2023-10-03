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

from aap_eda.core import models


class ActivationFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Filter by activation name.",
    )
    status = django_filters.CharFilter(
        field_name="status",
        lookup_expr="istartswith",
        label="Filter by activation status.",
    )
    decision_environment_id = django_filters.NumberFilter(
        field_name="decision_environment_id",
        lookup_expr="exact",
        label="Filter by Decision Environment ID.",
    )
    credential_id = django_filters.NumberFilter(
        field_name="decision_environment__credential_id",
        lookup_expr="exact",
        label="Filter by Credential ID.",
    )

    class Meta:
        model = models.Activation
        fields = ["name", "status", "decision_environment_id", "credential_id"]


class ActivationInstanceFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Filter by activation instance name.",
    )
    status = django_filters.CharFilter(
        field_name="status",
        lookup_expr="istartswith",
        label="Filter by activation instance status.",
    )

    class Meta:
        model = models.ActivationInstance
        fields = ["name", "status"]


class ActivationInstanceLogFilter(django_filters.FilterSet):
    log = django_filters.CharFilter(
        field_name="log",
        lookup_expr="icontains",
        label="Filter by activation instance log.",
    )

    class Meta:
        model = models.ActivationInstanceLog
        fields = ["log"]
