#  Copyright 2023 Red Hat, Inc.
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

from aap_eda.core.enums import ImagePullPolicy


def convert_pull_policy_to_frontend(pull_policy: str) -> str:
    """Convert internal pull policy enum to frontend-friendly string."""
    policy_mapping = {
        ImagePullPolicy.ALWAYS: "always",
        ImagePullPolicy.NEVER: "never",
        ImagePullPolicy.IF_NOT_PRESENT: "missing",
    }
    return policy_mapping.get(pull_policy, "always")


def convert_pull_policy_from_frontend(pull_policy: str) -> str:
    """Convert frontend-friendly string to internal pull policy enum."""
    if not pull_policy:
        return pull_policy

    frontend_mapping = {
        "always": ImagePullPolicy.ALWAYS,
        "never": ImagePullPolicy.NEVER,
        "missing": ImagePullPolicy.IF_NOT_PRESENT,
        # Also accept internal values (for backward compatibility)
        ImagePullPolicy.ALWAYS: ImagePullPolicy.ALWAYS,
        ImagePullPolicy.NEVER: ImagePullPolicy.NEVER,
        ImagePullPolicy.IF_NOT_PRESENT: ImagePullPolicy.IF_NOT_PRESENT,
    }
    return frontend_mapping.get(pull_policy, pull_policy)
