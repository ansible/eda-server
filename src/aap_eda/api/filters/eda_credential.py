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

import django_filters

from aap_eda.core import models


class EdaCredentialFilter(django_filters.FilterSet):
    @staticmethod
    def _split_csv_values(value):
        return [v.strip() for v in value.split(",") if v.strip()]

    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="istartswith",
        label="Filter by EDA credential name.",
    )
    credential_type_id = django_filters.NumberFilter(
        field_name="credential_type_id",
        lookup_expr="exact",
        label="Filter by Credential Type ID.",
    )
    credential_type__namespace__in = django_filters.CharFilter(
        field_name="credential_type__namespace",
        lookup_expr="in",
        label="Filter by Credential Type namespace (comma-separated).",
        method="filter_namespace_in",
    )
    credential_type__namespace__not_in = django_filters.CharFilter(
        field_name="credential_type__namespace",
        lookup_expr="in",
        label="Exclude Credential Type namespaces (comma-separated).",
        method="filter_namespace_not_in",
    )
    credential_type__kind = django_filters.CharFilter(
        field_name="credential_type__kind",
        lookup_expr="exact",
        label="Filter by Credential Type kind.",
        method="filter_kind",
    )
    credential_type__kind__in = django_filters.CharFilter(
        field_name="credential_type__kind",
        lookup_expr="in",
        label="Filter by Credential Type kind (comma-separated).",
        method="filter_kind_in",
    )

    def filter_namespace_in(self, queryset, name, value):
        """Filter by namespace with comma-separated values."""
        if value:
            namespaces = self._split_csv_values(value)
            if namespaces:
                return queryset.filter(
                    credential_type__namespace__in=namespaces
                )
        return queryset

    def filter_namespace_not_in(self, queryset, name, value):
        """Exclude credentials with specified namespaces."""
        if value:
            namespaces = self._split_csv_values(value)
            if namespaces:
                return queryset.exclude(
                    credential_type__namespace__in=namespaces
                )
        return queryset

    def filter_kind(self, queryset, name, value):
        """Filter by kind, supporting multiple values via repeated params."""
        # Get all 'credential_type__kind' values from query params
        request = self.request
        kind_values = request.GET.getlist("credential_type__kind")

        if len(kind_values) > 1:
            # Multiple kinds specified - use OR logic
            return queryset.filter(credential_type__kind__in=kind_values)
        elif value:
            # Single kind specified
            return queryset.filter(credential_type__kind=value)
        return queryset

    def filter_kind_in(self, queryset, name, value):
        """Filter by kind with comma-separated values."""
        if value:
            kinds = self._split_csv_values(value)
            if kinds:
                return queryset.filter(credential_type__kind__in=kinds)
        return queryset

    class Meta:
        model = models.EdaCredential
        fields = [
            "name",
            "credential_type_id",
            "credential_type__namespace__in",
            "credential_type__namespace__not_in",
            "credential_type__kind",
            "credential_type__kind__in",
        ]
