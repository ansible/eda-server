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
from ansible_base.lib.dynamic_config import (
    export,
    factory,
    load_dab_settings,
    load_envvars,
    load_standard_settings_files,
)

from .post_load import post_loading

EDA_SETTINGS_FILE = "/etc/eda/settings.yaml"

DYNACONF = factory(
    __name__,
    "EDA",
    # Options passed directly to dynaconf
    environments=("production", "development", "testing"),
    settings_files=["defaults.py"],
)

DYNACONF.load_file(EDA_SETTINGS_FILE)
load_standard_settings_files(
    DYNACONF
)  # /etc/ansible-automation-platform/*.yaml
load_envvars(DYNACONF)  # load envvars prefixed with EDA_
DYNACONF.load_file("constants.py")  # load internal non-overwritable settings
post_loading(DYNACONF)
load_dab_settings(DYNACONF)
export(__name__, DYNACONF)  # export back to django.conf.settings
