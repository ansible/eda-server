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

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from aap_eda.core.models import Setting
from aap_eda.core.utils.crypto.base import SecretValue

ENCRYPTED_STRING = "$encrypted$"


class InvalidKeyError(Exception):
    ...


class InvalidValueError(Exception):
    ...


@dataclass
class RegistryData(object):
    name: str
    default: Any
    type: type = str
    read_only: bool = False
    is_secret: bool = False


_APPLICATION_SETTING_REGISTRIES = [
    RegistryData(
        name="INSIGHTS_TRACKING_STATE",
        type=bool,
        default=False,
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_URL",
        read_only=True,
        default=settings.AUTOMATION_ANALYTICS_URL,
    ),
    RegistryData(
        name="REDHAT_USERNAME",
        default="",
    ),
    RegistryData(
        name="REDHAT_PASSWORD",
        is_secret=True,
        default="",
    ),
    RegistryData(
        name="SUBSCRIPTIONS_USERNAME",
        default="",
    ),
    RegistryData(
        name="SUBSCRIPTIONS_PASSWORD",
        is_secret=True,
        default="",
    ),
    RegistryData(
        name="INSIGHTS_CERT_PATH",
        read_only=True,
        default=settings.INSIGHTS_CERT_PATH,
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_LAST_GATHER",
        default="",
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_LAST_ENTRIES",
        default="{}",  # noqa P103
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_GATHER_INTERVAL",
        type=int,
        default=14400,
    ),
]


class SettingsRegistry(object):
    def __init__(self):
        self._registry = OrderedDict()
        for registry_data in _APPLICATION_SETTING_REGISTRIES:
            self.register(registry_data)

    def register(self, registry_data: RegistryData) -> None:
        if registry_data.name in self._registry:
            raise ImproperlyConfigured(
                f"Setting {registry_data.name} is already registered."
            )
        self._registry[registry_data.name] = registry_data

    def persist_registry_data(self):
        for key, data in self._registry.items():
            if data.read_only:
                update_method = Setting.objects.update_or_create
            else:
                update_method = Setting.objects.get_or_create
            update_method(key=key, defaults={"value": data.default})

    def get_registered_settings(
        self, skip_read_only: bool = False
    ) -> list[str]:
        setting_names = []

        for setting, data in self._registry.items():
            if data.read_only and skip_read_only:
                continue
            setting_names.append(setting)
        return setting_names

    def is_setting_secret(self, key: str) -> bool:
        return self._registry[key].is_secret

    def is_setting_read_only(self, key: str) -> bool:
        return self._registry[key].read_only

    def get_setting_type(self, key: str) -> type:
        return self._registry[key].type

    def db_update_setting(self, key: str, value: Any) -> None:
        self.db_update_settings({key: value})

    def db_update_settings(self, settings: dict[str, Any]) -> None:
        interval = None
        with transaction.atomic():
            for key, value in settings.items():
                self._validate_key(key, writable=True)
                Setting.objects.filter(key=key).update(
                    value=self._setting_value(key, value)
                )
                if key == "AUTOMATION_ANALYTICS_GATHER_INTERVAL":
                    interval = int(value)
        if interval:
            SettingsRegistry._reschedule_gather_analytics(interval)

    def db_get_settings_for_display(self) -> dict[str, Any]:
        keys = self.get_registered_settings()
        settings = Setting.objects.filter(key__in=keys)
        return {
            obj.key: self._value_for_display(obj.key, obj.value)
            for obj in settings
        }

    def db_get_setting(self, key: str) -> Any:
        self._validate_key(key)
        setting = Setting.objects.filter(key=key).first()
        return self._decrypt_value(key, setting.value)

    def _validate_key(self, key: str, writable: bool = False) -> None:
        if key not in self._registry:
            raise InvalidKeyError(f"{key} is not a preset key")
        if writable and self.is_setting_read_only(key):
            raise InvalidKeyError(f"{key} is readonly")

    def _decrypt_value(self, key: str, db_value: SecretValue) -> Any:
        val = db_value.get_secret_value()
        if val != "":
            val = yaml.safe_load(val)
        return self._setting_value(key, val)

    def _setting_value(self, key: str, value: Any) -> Any:
        try:
            return self.get_setting_type(key)(value)
        except (ValueError, TypeError):
            raise InvalidValueError(
                f"Attempt to set an invalid value to key {key}"
            )

    def _value_for_display(self, key: str, db_value: SecretValue) -> Any:
        value = self._decrypt_value(key, db_value)
        if self.is_setting_secret(key) and value:
            return ENCRYPTED_STRING
        return value

    @staticmethod
    def _reschedule_gather_analytics(interval: int):
        from aap_eda.tasks.analytics import reschedule_gather_analytics

        reschedule_gather_analytics(interval)


settings_registry = SettingsRegistry()
