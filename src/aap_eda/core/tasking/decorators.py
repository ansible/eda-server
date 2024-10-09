"""Tools for running background tasks."""
from __future__ import annotations

import functools
import logging
import time
import typing

import redis

logger = logging.getLogger(__name__)


def redis_connect_retry(
    max_delay: int = 60,
    loop_exit: typing.Optional[typing.Callable[[Exception], bool]] = None,
) -> typing.Callable:
    max_delay = max(max_delay, 1)

    def decorator(func: typing.Callable) -> typing.Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> typing.Optional[typing.Any]:
            value = None
            delay = 1
            while True:
                try:
                    value = func(*args, **kwargs)
                    if delay > 1:
                        logger.info("Connection to redis re-established.")
                    break
                except (
                    redis.exceptions.ClusterDownError,
                    redis.exceptions.ConnectionError,
                    redis.exceptions.RedisClusterException,
                    redis.exceptions.TimeoutError,
                ) as e:
                    # There are a lot of different exceptions that inherit from
                    # ConnectionError.  So we need to make sure if we got that
                    # its an actual ConnectionError. If not, go ahead and raise
                    # it.
                    # Note:  ClusterDownError and TimeoutError are not
                    #        subclasses of ConnectionError.
                    if (
                        isinstance(e, redis.exceptions.ConnectionError)
                        and type(e) is not redis.exceptions.ConnectionError
                    ):
                        raise

                    # RedisClusterException is used as a catch-all for various
                    # faults.  The only one we should tolerate is that which
                    # includes "Redis Cluster cannot be connected." which is
                    # experienced when there are zero cluster hosts that can be
                    # reached.
                    if isinstance(
                        e, redis.exceptions.RedisClusterException
                    ) and ("Redis Cluster cannot be connected." not in str(e)):
                        raise

                    if (loop_exit is not None) and loop_exit(e):
                        break

                    delay = min(delay, max_delay)
                    logger.error(
                        f"Connection to redis failed; retrying in {delay}s."
                    )
                    time.sleep(delay)

                    delay *= 2
            return value

        return wrapper

    return decorator
