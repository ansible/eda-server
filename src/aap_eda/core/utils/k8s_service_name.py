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

import re
import uuid


def create_k8s_service_name(activation_name: str) -> str:
    """Attempt to convert the activation name to a 1035 name.

    Convert non qualified letters to - and convert it to lowercase
    """
    name = re.sub(r"[^a-z0-9\-]+", "-", activation_name.lower())
    name = re.sub(r"^[0-9-]+", "", name.rstrip("-"))
    if len(name) > 63:
        name = f"{name[0:61]}-{name[-1]}"

    if not name:
        name = f"service-{uuid.uuid4()}"
    return name


def is_rfc_1035_compliant(name: str) -> bool:
    """Check if name is compatible with RFC 1035.

    - contain at most 63 characters
    - contain only lowercase alphanumeric characters or '-'
    - start with an alphabetic character
    - end with an alphanumeric character
    """
    qualified_pattern = re.compile(r"^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$")

    return re.match(qualified_pattern, name) is not None
