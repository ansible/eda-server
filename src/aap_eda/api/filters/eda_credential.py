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

    class Meta:
        model = models.EdaCredential
        fields = ["name", "credential_type_id"]
