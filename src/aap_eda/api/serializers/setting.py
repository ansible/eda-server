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

from aap_eda.conf import settings_registry


class SettingSerializer(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super(SettingSerializer, self).__init__(*args, **kwargs)

        for key in settings_registry.get_registered_settings():
            v_type = settings_registry.get_setting_type(key)
            read_only = settings_registry.is_setting_read_only(key)
            if v_type == str:
                field = serializers.CharField(
                    required=False, allow_blank=True, read_only=read_only
                )
            elif v_type == int:
                field = serializers.IntegerField(
                    required=False, read_only=read_only
                )
            elif v_type == bool:
                field = serializers.BooleanField(
                    required=False, read_only=read_only
                )
            elif v_type == dict:
                field = serializers.JSONField(
                    required=False, read_only=read_only
                )
            else:
                raise TypeError(f"unsupported type {v_type}")
            self.fields[key] = field
