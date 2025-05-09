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

from typing import Any

from django.conf import settings
from flags.state import flag_enabled

DISPATCHERD: bool
ANALYTICS: bool

_caches = {}


def _get_feature(name: str):
    if name not in _caches:
        _caches[name] = flag_enabled(name)
    return _caches[name]


def __getattr__(name: str) -> Any:
    if name == "DISPATCHERD":
        return _get_feature(settings.DISPATCHERD_FEATURE_FLAG_NAME)
    elif name == "ANALYTICS":
        return _get_feature("FEATURE_EDA_ANALYTICS_ENABLED")
    raise AttributeError(f"module {__name__} has no attribute {name}")
