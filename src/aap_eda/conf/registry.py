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

import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

import requests
import yaml
from ansible_base.resource_registry import resource_server
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from aap_eda.core.models import Setting
from aap_eda.core.utils.crypto.base import SecretValue

RESYNC_INTERVAL = 10

logger = logging.getLogger(__name__)


class InvalidKeyError(Exception):
    ...


class InvalidValueError(Exception):
    ...


@dataclass
class RegistryData(object):
    name: str
    default: Any
    label: str = ""
    help_text: str = ""
    type: type = str
    is_secret: bool = False
    hidden: bool = False
    defined_in_file: bool = False
    category: str = "System"
    category_slug = "system"
    unit: str = ""
    sync_group: str = ""
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


_APPLICATION_SETTING_REGISTRIES = [
    RegistryData(
        name="INSIGHTS_TRACKING_STATE",
        type=bool,
        default=False,
        label="Gather data for Automation Analytics",
        help_text="Enables the service to gather data on automation and send it to Automation Analytics.",  # noqa: E501
        sync_group="_GATEWAY_ANALYTICS_SETTING_SYNC",
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_URL",
        default=settings.AUTOMATION_ANALYTICS_URL,
        defined_in_file=True,
        label="Automation Analytics upload URL",
        help_text="This value has been set manually in a settings file.\n\nThis setting is used to to configure the upload URL for data collection for Automation Analytics.",  # noqa: E501
    ),
    RegistryData(
        name="REDHAT_USERNAME",
        default="",
        label="Red Hat customer username",
        help_text="This username is used to send data to Automation Analytics",
        sync_group="_GATEWAY_ANALYTICS_SETTING_SYNC",
    ),
    RegistryData(
        name="REDHAT_PASSWORD",
        is_secret=True,
        default="",
        label="Red Hat customer password",
        help_text="This password is used to send data to Automation Analytics",
        sync_group="_GATEWAY_ANALYTICS_SETTING_SYNC",
    ),
    RegistryData(
        name="SUBSCRIPTIONS_USERNAME",
        default="",
        label="Red Hat or Satellite username",
        help_text="This username is used to retrieve subscription and content information",  # noqa: E501
        sync_group="_GATEWAY_ANALYTICS_SETTING_SYNC",
    ),
    RegistryData(
        name="SUBSCRIPTIONS_PASSWORD",
        is_secret=True,
        default="",
        label="Red Hat or Satellite password",
        help_text="This password is used to retrieve subscription and content information",  # noqa: E501
        sync_group="_GATEWAY_ANALYTICS_SETTING_SYNC",
    ),
    RegistryData(
        name="INSIGHTS_CERT_PATH",
        default=settings.INSIGHTS_CERT_PATH,
        hidden=True,
        defined_in_file=True,
        label="Insights certificate path",
        help_text="File path to locate insights certificate",
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_LAST_GATHER",
        default="",
        hidden=True,
        label="Last gather date for Automation Analytics",
        help_text="",
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_LAST_ENTRIES",
        default="{}",  # noqa P103
        label="Last gathered entries from the data collection service of Automation Analytics",  # noqa: E501
        help_text="",
    ),
    RegistryData(
        name="AUTOMATION_ANALYTICS_GATHER_INTERVAL",
        type=int,
        default=14400,
        label="Automation Analytics Gather Interval",
        help_text="Interval (in seconds) between data gathering.",
        sync_group="_GATEWAY_ANALYTICS_SETTING_SYNC",
    ),
    RegistryData(
        name="_GATEWAY_ANALYTICS_SETTING_SYNC_SLUG",
        default="api/gateway/v1/settings/analytics/",
        hidden=True,
        label="slug to fetch analytics settings in gateway",
        help_text="",
    ),
    RegistryData(
        name="_GATEWAY_ANALYTICS_SETTING_SYNC_TIME",
        type=int,
        default=0,
        hidden=True,
        label="Time when analytics settings are fetched",
        help_text="",
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
            if data.defined_in_file:
                update_method = Setting.objects.update_or_create
            else:
                update_method = Setting.objects.get_or_create
            update_method(key=key, defaults={"value": data.default})

    def get_setting_schemas(self) -> OrderedDict[str, RegistryData]:
        return self._registry

    def get_registered_settings(
        self, skip_read_only: bool = False
    ) -> list[str]:
        setting_names = []

        for setting, data in self._registry.items():
            if data.defined_in_file and skip_read_only:
                continue
            setting_names.append(setting)
        return setting_names

    def is_setting_secret(self, key: str) -> bool:
        return self._registry[key].is_secret

    def is_setting_read_only(self, key: str) -> bool:
        setting = self._registry[key]
        return setting.defined_in_file or bool(setting.sync_group)

    def get_setting_type(self, key: str) -> type:
        return self._registry[key].type

    def db_update_setting(self, key: str, value: Any) -> None:
        self._validate_key(key, writable=True)
        self._db_update_settings({key: value})

    def _db_update_settings(self, settings_dict: dict[str, Any]) -> None:
        with transaction.atomic():
            for key, value in settings_dict.items():
                Setting.objects.filter(key=key).update(
                    value=self._setting_value(key, value)
                )

    def db_get_setting(self, key: str, sync: bool = True) -> Any:
        self._validate_key(key)
        if sync and self._registry[key].sync_group:
            self._resync_remote_settings(self._registry[key].sync_group)
        setting = Setting.objects.filter(key=key).first()
        return self._decrypt_value(key, setting.value)

    def _resync_remote_settings(self, sync_group: str) -> None:
        if (
            not settings.RESOURCE_SERVER["URL"]
            or not settings.RESOURCE_SERVER["SECRET_KEY"]
        ):
            logger.info(
                "Resource Server not configured. "
                "Skip resyncing remote settings."
            )
            return
        time_key = f"{sync_group}_TIME"
        sync_at = self._decrypt_value(
            time_key, Setting.objects.filter(key=time_key).first().value
        )
        now = timezone.now().timestamp()
        if now - sync_at < RESYNC_INTERVAL:
            return

        slug_key = f"{sync_group}_SLUG"
        sync_slug = self._decrypt_value(
            slug_key, Setting.objects.filter(key=slug_key).first().value
        )
        url = f"{settings.RESOURCE_SERVER['URL']}/{sync_slug}"
        token = resource_server.get_service_token()
        logger.info(f"Getting remote settings from {url}")
        res = requests.get(
            url,
            headers={"X-ANSIBLE-SERVICE-AUTH": token},
            verify=settings.RESOURCE_SERVER["VALIDATE_HTTPS"],
        )
        if not res.ok:
            msg = (
                "Failed to fetch settings from gateway. Status code"
                f"{res.status_code}. Default or stored values will be used"
            )
            logger.error(msg)
            return
        gw_settings = {
            key: value
            for key, value in res.json().items()
            if key in self._registry
        }
        gw_settings[time_key] = now
        self._db_update_settings(gw_settings)

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


settings_registry = SettingsRegistry()
