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

from functools import cache
from typing import Any, Dict

from django.conf import settings
from flags.state import flag_enabled

# Type hints for module attributes
ANALYTICS: bool

# Mapping of feature names to their corresponding setting names
_FEATURE_FLAGS: Dict[str, str] = {
    "ANALYTICS": "ANALYTICS_FEATURE_FLAG_NAME",
}


@cache
def _get_feature(name: str) -> bool:
    """Get the current value of a feature flag."""
    return flag_enabled(name)


def __getattr__(name: str) -> Any:
    """Dynamically provide access to feature flags as module attributes."""
    try:
        setting_name = _FEATURE_FLAGS[name]
        return _get_feature(getattr(settings, setting_name))
    except KeyError:
        raise AttributeError(
            f"module {__name__} has no attribute {name}"
        ) from None
