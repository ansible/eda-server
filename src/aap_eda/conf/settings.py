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

from typing import Any

from aap_eda.conf.registry import settings_registry


class ApplicationSettings(object):
    def __setattr__(self, name: str, value: Any) -> None:
        settings_registry.db_update_setting(name, value)

    def __getattr__(self, name: str) -> Any:
        return settings_registry.db_get_setting(name)


application_settings = ApplicationSettings()
