#  Copyright 2025 Red Hat, Inc.
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


class CredentialInputSourceFilter(django_filters.FilterSet):
    source_credential = django_filters.NumberFilter(
        field_name="source_credential",
        lookup_expr="exact",
        label="Filter by Source Credential ID.",
    )
    target_credential = django_filters.NumberFilter(
        field_name="target_credential",
        lookup_expr="exact",
        label="Filter by Target Credential ID.",
    )

    class Meta:
        model = models.CredentialInputSource
        fields = ["target_credential", "source_credential"]
