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

import time

import pytest
import redis

from aap_eda.core import tasking


@pytest.fixture
def tasking_caplog(caplog_factory):
    return caplog_factory(tasking.logger)


def test_max_delay(tasking_caplog):
    """Tests that the specification of a maximum delay value is respected and
    used."""

    # The sleep between retries grows exponentially as 1, 2, 4, 8, 16, 32 and
    # is then capped at a default of 60.
    #
    # This test will loop sufficiently to reach 60 multiple times but will
    # specify a cap of 5.
    loop_count = 0
    loop_limit = 8

    @tasking.redis_connect_retry(max_delay=5)
    def _test_function():
        nonlocal loop_count

        loop_count += 1
        if loop_count >= (loop_limit + 1):
            return

        time.sleep(1)
        raise redis.exceptions.ConnectionError

    _test_function()

    assert "Connection to redis failed; retrying in 5s." in tasking_caplog.text
    assert (
        "Connection to redis failed; retrying in 60s."
        not in tasking_caplog.text
    )


@pytest.mark.parametrize(
    ("exception"),
    [
        redis.exceptions.ClusterDownError,
        redis.exceptions.ConnectionError,
        redis.exceptions.TimeoutError,
    ],
)
def test_retry_exceptions(exception):
    """Tests that the exceptions to be tolerated for retry are tolerated and
    that any subclass of redis.exceptions.ConnectionError is raised rather than
    tolerated."""

    loop_count = 0
    loop_limit = 2

    class SubclassConnectionError(redis.exceptions.ConnectionError):
        pass

    @tasking.redis_connect_retry()
    def _test_function():
        nonlocal loop_count

        loop_count += 1
        if loop_count >= (loop_limit + 1):
            raise SubclassConnectionError

        time.sleep(1)
        raise exception(type(exception))

    with pytest.raises(SubclassConnectionError):
        _test_function()


def test_loop_exit():
    """Tests that the specification of a loop exit function is respected and
    used."""

    loop_count = 0
    loop_limit = 2

    class LoopLimitExceeded(Exception):
        pass

    @tasking.redis_connect_retry(loop_exit=lambda e: loop_count >= loop_limit)
    def _test_function():
        nonlocal loop_count

        loop_count += 1
        if loop_count >= (loop_limit + 1):
            raise LoopLimitExceeded

        time.sleep(1)
        raise redis.exceptions.ConnectionError

    _test_function()
