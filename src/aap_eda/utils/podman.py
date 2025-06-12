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
from typing import Optional


# temporary parser until bug is fixed in podman-py
# https://github.com/containers/podman-py/pull/555
def parse_repository(name: str) -> tuple[str, Optional[str]]:
    """Parse repository image name from tag or digest.

    Returns:
        item 1: repository name
        item 2: Either tag or None
    """
    # split repository and image name from tag
    # tags need to be split from the right since
    # a port number might increase the split list len by 1
    elements = name.rsplit(":", 1)
    if len(elements) == 2 and "/" not in elements[1]:
        return elements[0], elements[1]

    return name, None
