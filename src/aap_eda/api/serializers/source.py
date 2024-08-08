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

from rest_framework import serializers

from aap_eda.api.serializers.fields.yaml import YAMLSerializerField


class SourceSerializer(serializers.Serializer):
    name = serializers.CharField(
        required=True,
        help_text="Name of the source",
    )

    source_info = YAMLSerializerField(
        required=True,
        help_text="The information about the source",
        sort_keys=False,
    )

    rulebook_hash = serializers.CharField(
        required=True,
        help_text="Hash of the rulebook",
    )
