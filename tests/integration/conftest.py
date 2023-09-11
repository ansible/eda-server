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

import pytest
from pytest_redis import factories

from aap_eda.core.tasking import Queue

ADMIN_USERNAME = "test.admin"
ADMIN_PASSWORD = "test.admin.123"


# fixture for pytest-redis plugin
# like django-db for a running redis server
redis_external = factories.redisdb("redis_nooproc")


@pytest.fixture
def default_queue(redis_external) -> Queue:
    return Queue("default", connection=redis_external)
