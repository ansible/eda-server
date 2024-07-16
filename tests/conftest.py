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
import redis

from aap_eda.settings import default


#################################################################
# Redis
#################################################################
@pytest.fixture
def redis_parameters() -> dict:
    """Provide redis parameters based on settings values."""
    params = (
        default._rq_common_parameters() | default._rq_redis_client_parameters()
    )

    # Convert to lowercase for use in establishing a redis client.
    params = {k.lower(): v for (k, v) in params.items()}

    # We try to avoid conflicting with a deployed environment by using a
    # different database from that of the settings.
    # This is not guaranteed as the deployed environment could be differently
    # configured from the default, but in development it should be fine.
    client = redis.Redis(**params)
    max_dbs = int(client.config_get("databases")["databases"])
    params["db"] = (params["db"] + 1) % max_dbs

    return params
