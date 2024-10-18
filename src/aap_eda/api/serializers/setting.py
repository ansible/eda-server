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

        for setting in settings_registry.get_setting_schemas().values():
            common_attrs = {
                "required": False,
                "read_only": setting.defined_in_file,
                "label": setting.label,
                "help_text": setting.help_text,
                "default": setting.default,
            }
            v_type = setting.type
            if setting.type == str:
                common_attrs["min_length"] = setting.min_length
                common_attrs["max_length"] = setting.max_length
                field = serializers.CharField(allow_blank=True, **common_attrs)
            elif v_type == int:
                common_attrs["min_value"] = setting.min_value
                common_attrs["max_value"] = setting.max_value
                field = serializers.IntegerField(**common_attrs)
            elif v_type == bool:
                field = serializers.BooleanField(**common_attrs)
            elif v_type == dict:
                field = serializers.JSONField(**common_attrs)
            else:
                raise TypeError(f"unsupported type {v_type}")
            field.category = setting.category
            field.category_slug = setting.category_slug
            field.defined_in_file = setting.defined_in_file
            field.hidden = setting.hidden
            field.encrypted = setting.is_secret
            if setting.unit:
                field.unit = setting.unit
            self.fields[setting.name] = field
