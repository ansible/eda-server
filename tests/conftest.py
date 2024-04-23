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

import pytest

from aap_eda.settings import default


@pytest.fixture
def redis_parameters() -> dict:
    """Provide redis parameters based on settings values."""
    params = (
        default._rq_common_parameters() | default._rq_redis_client_parameters()
    )
    # Convert to lowercase for use in establishing a redis client.
    return {k.lower(): v for (k, v) in params.items()}
