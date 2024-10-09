"""Tools for running background tasks."""
from __future__ import annotations

import logging
import typing
from datetime import datetime, timedelta
from types import MethodType

import django_rq
import rq
import rq_scheduler
from ansible_base.lib import constants
from ansible_base.lib.redis.client import (
    DABRedis,
    DABRedisCluster,
    get_redis_client as _get_redis_client,
    get_redis_status as _get_redis_status,
)
from django.conf import settings
from rq import results as rq_results

from aap_eda.settings import default

# from .decorators import redis_connect_retry

logger = logging.getLogger(__name__)

ErrorHandlerType = typing.Callable[[rq.job.Job], None]

_ErrorHandlersArgType = typing.Union[
    list[ErrorHandlerType],
    tuple[ErrorHandlerType],
    ErrorHandlerType,
    None,
]


def _create_url_from_parameters(**kwargs) -> str:
    # Make the URL that DAB will expect for instantiation.
    schema = "unix"
    try:
        path = kwargs["unix_socket_path"]
    except KeyError:
        schema = "redis"
        if kwargs.get("ssl", False):
            schema = "rediss"
        path = f"{kwargs.get('host')}:{kwargs.get('port')}"

    url = f"{schema}://{path}"
    return url


def _prune_redis_kwargs(**kwargs) -> dict[str, typing.Any]:
    """Prunes the kwargs of unsupported parameters for RedisCluster."""
    # HA cluster does not support an alternate redis db and will generate an
    # exception if we pass a value (even the default). If we're in that
    # situation we drop the db and, if the db is anything other than the
    # default log an informational message.
    db = kwargs.get("db", None)
    if (db is not None) and (kwargs.get("mode", "") == "cluster"):
        del kwargs["db"]
        if db != default.DEFAULT_REDIS_DB:
            logger.info(
                f"clustered redis supports only the default db"
                f"; db specified: {db}"
            )
    return kwargs


def get_redis_client(**kwargs) -> typing.Union[DABRedis, DABRedisCluster]:
    """Instantiate a Redis client via DAB.

    DAB will return an appropriate client for HA based on the passed
    parameters.
    """
    kwargs = _prune_redis_kwargs(**kwargs)
    return _get_redis_client(_create_url_from_parameters(**kwargs), **kwargs)


def get_redis_status() -> dict:
    """Query DAB for the status of Redis."""
    kwargs = default.rq_redis_client_instantiation_parameters()
    kwargs = _prune_redis_kwargs(**kwargs)
    return _get_redis_status(_create_url_from_parameters(**kwargs), **kwargs)


def is_redis_failed() -> bool:
    """Return a boolean indicating if Redis is in a failed state."""
    response = get_redis_status()
    status = response["status"]
    logger.debug(f"Redis status: {status}")
    return status == constants.STATUS_FAILED


class Scheduler(rq_scheduler.Scheduler):
    """Custom scheduler class."""

    def __init__(
        self,
        queue_name="default",
        queue=None,
        interval=60,
        connection=None,
        job_class=None,
        queue_class=None,
        name=None,
    ):
        connection = _get_necessary_client_connection(connection)
        super().__init__(
            queue_name=queue_name,
            queue=queue,
            interval=interval,
            connection=connection,
            job_class=job_class,
            queue_class=queue_class,
            name=name,
        )


def enable_redis_prefix():
    redis_prefix = settings.RQ_REDIS_PREFIX

    # Job.
    rq.job.Job.redis_job_namespace_prefix = f"{redis_prefix}:job:"

    rq.registry.BaseRegistry.key_template = f"{redis_prefix}:registry:{0}"
    rq.registry.CanceledJobRegistry.key_template = (
        f"{redis_prefix}:canceled:{0}"
    )
    rq.registry.DeferredJobRegistry.key_template = (
        f"{redis_prefix}:deferred:{0}"
    )
    rq.registry.FailedJobRegistry.key_template = f"{redis_prefix}:failed:{0}"
    rq.registry.FinishedJobRegistry.key_template = (
        f"{redis_prefix}:finished:{0}"
    )
    rq.registry.StartedJobRegistry.key_template = f"{redis_prefix}:wip:{0}"
    rq.registry.ScheduledJobRegistry.key_template = (
        f"{redis_prefix}:scheduled:{0}"
    )

    # PubSub.
    rq.command.PUBSUB_CHANNEL_TEMPLATE = f"{redis_prefix}:pubsub:%s"

    # Queue.
    rq.queue.Queue.redis_queue_namespace_prefix = f"{redis_prefix}:queue:"
    rq.queue.Queue.redis_queues_keys = f"{redis_prefix}:queues"

    # Worker.
    # Although PUBSUB_CHANNEL_TEMPLATE is defined in rq.command (and we've
    # overridden it there for any new uses) rq.worker, which we've already
    # imported, imports it so we need to override that value as well.
    rq.worker.PUBSUB_CHANNEL_TEMPLATE = rq.command.PUBSUB_CHANNEL_TEMPLATE
    rq.worker.Worker.redis_worker_namespace_prefix = f"{redis_prefix}:worker:"
    rq.worker.Worker.redis_workers_keys = f"{redis_prefix}:workers"
    rq.worker_registration.REDIS_WORKER_KEYS = f"{redis_prefix}:workers"
    rq.worker_registration.WORKERS_BY_QUEUE_KEY = f"{redis_prefix}:workers:%s"
    rq.suspension.WORKERS_SUSPENDED = f"{redis_prefix}:suspended"

    # Scheduler.
    Scheduler.redis_scheduler_namespace_prefix = (
        f"{redis_prefix}:scheduler_instance:"
    )
    Scheduler.scheduler_key = f"{redis_prefix}:scheduler"
    Scheduler.scheduler_lock_key = f"{redis_prefix}:scheduler_lock"
    Scheduler.scheduled_jobs_key = f"{redis_prefix}:scheduler:scheduled_jobs"

    def eda_get_key(job_id):
        return f"{redis_prefix}:results:{job_id}"

    rq_results.get_key = eda_get_key

    def cls_get_key(cls, job_id):
        return f"{redis_prefix}:results:{job_id}"

    rq_results.Result.get_key = MethodType(cls_get_key, rq_results.Result)

    def property_registry_cleaning_key(self):
        return f"{redis_prefix}:clean_registries:{self.name}"

    setattr(  # noqa: B010
        rq.queue.Queue,
        "registry_cleaning_key",
        property(property_registry_cleaning_key),
    )


enable_redis_prefix()


class SerializerProtocol(typing.Protocol):
    @staticmethod
    def dumps(obj: typing.Any) -> bytes:
        ...

    @staticmethod
    def loads(data: bytes) -> typing.Any:
        ...


class Queue(django_rq.queues.Queue):
    """Custom queue class.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        name: str = "default",
        default_timeout: int = -1,
        connection: typing.Optional[rq.Connection] = None,
        is_async: bool = True,
        job_class: typing.Optional[rq.job.Job] = None,
        serializer: typing.Optional[SerializerProtocol] = None,
        **kwargs: typing.Any,
    ):
        if serializer is None:
            serializer = rq.serializers.JSONSerializer

        super().__init__(
            name=name,
            default_timeout=default_timeout,
            connection=_get_necessary_client_connection(connection),
            is_async=is_async,
            job_class=job_class,
            serializer=serializer,
            **kwargs,
        )


class Job(rq.job.Job):
    """Custom job class.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        id: typing.Optional[str] = None,
        connection: typing.Optional[rq.Connection] = None,
        serializer: typing.Optional[SerializerProtocol] = None,
    ):
        if serializer is None:
            serializer = rq.serializers.JSONSerializer
        connection = _get_necessary_client_connection(connection)

        super().__init__(id, connection, serializer)


# django-rq's rqworker command does not support --connection-class so
# we cannot specify the DAB redis client that way.  Even if it did we
# couldn't use it as DAB requires a url parameter that Redis does not.
# If the connection a worker is given is not from DAB we replace it
# with one that is.
def _get_necessary_client_connection(
    connection: rq.Connection,
) -> rq.Connection:
    if not isinstance(connection, (DABRedis, DABRedisCluster)):
        connection = get_redis_client(
            **default.rq_redis_client_instantiation_parameters()
        )
    return connection


class Worker(rq.Worker):
    """Custom worker class.

    Provides establishment of DAB Redis client and work arounds for various
    DABRedisCluster issues.
    """

    def __init__(
        self,
        queues: typing.Iterable[typing.Union[Queue, str]],
        name: typing.Optional[str] = None,
        default_result_ttl: int = rq.defaults.DEFAULT_RESULT_TTL,
        connection: typing.Optional[rq.Connection] = None,
        exc_handler: typing.Any = None,
        exception_handlers: _ErrorHandlersArgType = None,
        default_worker_ttl: int = rq.defaults.DEFAULT_WORKER_TTL,
        job_class: typing.Type[rq.job.Job] = None,
        queue_class: typing.Type[django_rq.queues.Queue] = None,
        log_job_description: bool = True,
        job_monitoring_interval: int = (
            rq.defaults.DEFAULT_JOB_MONITORING_INTERVAL
        ),
        disable_default_exception_handler: bool = False,
        prepare_for_work: bool = True,
        serializer: typing.Optional[SerializerProtocol] = None,
    ):
        connection = _get_necessary_client_connection(connection)
        super().__init__(
            queues=queues,
            name=name,
            default_result_ttl=default_result_ttl,
            connection=connection,
            exc_handler=exc_handler,
            exception_handlers=exception_handlers,
            default_worker_ttl=default_worker_ttl,
            job_class=job_class,
            queue_class=queue_class,
            log_job_description=log_job_description,
            job_monitoring_interval=job_monitoring_interval,
            disable_default_exception_handler=disable_default_exception_handler,  # noqa: E501
            prepare_for_work=prepare_for_work,
            serializer=rq.serializers.JSONSerializer,
        )
        self.is_shutting_down = False

    def _set_connection(
        self,
        connection: typing.Union[DABRedis, DABRedisCluster],
    ) -> typing.Union[DABRedis, DABRedisCluster]:
        # A DABRedis connection doesn't need intervention.
        if isinstance(connection, DABRedis):
            return super()._set_connection(connection)

        try:
            connection_pool = connection.connection_pool
            current_socket_timeout = connection_pool.connection_kwargs.get(
                "socket_timeout"
            )
            if current_socket_timeout is None:
                timeout_config = {"socket_timeout": self.connection_timeout}
                connection_pool.connection_kwargs.update(timeout_config)
        except AttributeError:
            nodes = connection.get_nodes()
            for node in nodes:
                connection_pool = node.redis_connection.connection_pool
                current_socket_timeout = connection_pool.connection_kwargs.get(
                    "socket_timeout"
                )
                if current_socket_timeout is None:
                    timeout_config = {
                        "socket_timeout": self.connection_timeout
                    }
                    connection_pool.connection_kwargs.update(timeout_config)
        return connection

    @classmethod
    def all(
        cls,
        connection: typing.Optional[
            typing.Union[DABRedis, DABRedisCluster]
        ] = None,
        job_class: typing.Optional[typing.Type[Job]] = None,
        queue_class: typing.Optional[typing.Type[Queue]] = None,
        queue: typing.Optional[Queue] = None,
        serializer=None,
    ) -> typing.List[Worker]:
        # If we don't have a queue (whose connection would be used) make
        # certain that we have an appropriate connection and pass it
        # to the superclass.
        if queue is None:
            connection = _get_necessary_client_connection(connection)
        return super().all(
            connection,
            job_class,
            queue_class,
            queue,
            serializer,
        )

    def handle_job_success(
        self,
        job: Job,
        queue: Queue,
        started_job_registry: rq.registry.StartedJobRegistry,
    ):
        # A DABRedis connection doesn't need intervention.
        if isinstance(self.connection, DABRedis):
            return super().handle_job_success(job, queue, started_job_registry)

        # For DABRedisCluster perform success handling.
        # DABRedisCluster doesn't provide the watch, multi, etc. methods
        # necessary for the superclass implementation, but we don't need
        # them as there's no dependencies in how we use the jobs.
        with self.connection.pipeline() as pipeline:
            self.set_current_job_id(None, pipeline=pipeline)
            self.increment_successful_job_count(pipeline=pipeline)
            self.increment_total_working_time(
                job.ended_at - job.started_at,
                pipeline,
            )

            result_ttl = job.get_result_ttl(self.default_result_ttl)
            if result_ttl != 0:
                job._handle_success(result_ttl, pipeline=pipeline)

            job.cleanup(result_ttl, pipeline=pipeline, remove_from_queue=False)
            started_job_registry.remove(job, pipeline=pipeline)

            pipeline.execute()

    def handle_warm_shutdown_request(self):
        self.is_shutting_down = True
        super().handle_warm_shutdown_request()

    # We are overriding the work function to utilize our own common
    # Redis connection looping.
    def work(
        self,
        burst: bool = False,
        logging_level: str = "INFO",
        date_format: str = rq.defaults.DEFAULT_LOGGING_DATE_FORMAT,
        log_format: str = rq.defaults.DEFAULT_LOGGING_FORMAT,
        max_jobs: typing.Optional[int] = None,
        with_scheduler: bool = False,
    ) -> bool:
        value = None
        while True:
#             value = redis_connect_retry(
#                 loop_exit=lambda e: self.is_shutting_down
#             )(super().work)(
            value = super().work(
                burst,
                logging_level,
                date_format,
                log_format,
                max_jobs,
                with_scheduler,
            )

            # If there's a return value or the worker is shutting down
            # break out of the loop.
            if (value is not None) or self.is_shutting_down:
                if value is not None:
                    logger.debug(f"Working exited normally with {value}")
                break

            logger.error(
                "Work exited no return value, going to restart the worker"
            )

        return value


class DefaultWorker(Worker):
    """Custom default worker class used for non-activation tasks.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        queues: typing.Iterable[typing.Union[Queue, str]],
        name: typing.Optional[str] = "default",
        default_result_ttl: int = rq.defaults.DEFAULT_RESULT_TTL,
        connection: typing.Optional[rq.Connection] = None,
        exc_handler: typing.Any = None,
        exception_handlers: _ErrorHandlersArgType = None,
        default_worker_ttl: int = rq.defaults.DEFAULT_WORKER_TTL,
        job_class: typing.Type[rq.job.Job] = None,
        queue_class: typing.Type[django_rq.queues.Queue] = None,
        log_job_description: bool = True,
        job_monitoring_interval: int = (
            rq.defaults.DEFAULT_JOB_MONITORING_INTERVAL
        ),
        disable_default_exception_handler: bool = False,
        prepare_for_work: bool = True,
        serializer: typing.Optional[SerializerProtocol] = None,
    ):
        if job_class is None:
            job_class = Job
        if queue_class is None:
            queue_class = Queue

        super().__init__(
            queues=queues,
            name=name,
            default_result_ttl=default_result_ttl,
            connection=connection,
            exc_handler=exc_handler,
            exception_handlers=exception_handlers,
            default_worker_ttl=default_worker_ttl,
            job_class=job_class,
            queue_class=queue_class,
            log_job_description=log_job_description,
            job_monitoring_interval=job_monitoring_interval,
            disable_default_exception_handler=disable_default_exception_handler,  # noqa: E501
            prepare_for_work=prepare_for_work,
            serializer=rq.serializers.JSONSerializer,
        )


class ActivationWorker(Worker):
    """Custom worker class used for activation related tasks.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        queues: typing.Iterable[typing.Union[Queue, str]],
        name: typing.Optional[str] = "activation",
        default_result_ttl: int = rq.defaults.DEFAULT_RESULT_TTL,
        connection: typing.Optional[rq.Connection] = None,
        exc_handler: typing.Any = None,
        exception_handlers: _ErrorHandlersArgType = None,
        default_worker_ttl: int = rq.defaults.DEFAULT_WORKER_TTL,
        job_class: typing.Type[rq.job.Job] = None,
        queue_class: typing.Type[django_rq.queues.Queue] = None,
        log_job_description: bool = True,
        job_monitoring_interval: int = (
            rq.defaults.DEFAULT_JOB_MONITORING_INTERVAL
        ),
        disable_default_exception_handler: bool = False,
        prepare_for_work: bool = True,
        serializer: typing.Optional[SerializerProtocol] = None,
    ):
        if job_class is None:
            job_class = Job
        if queue_class is None:
            queue_class = Queue
        queue_name = settings.RULEBOOK_QUEUE_NAME

        super().__init__(
            queues=[Queue(name=queue_name, connection=connection)],
            name=name,
            default_result_ttl=default_result_ttl,
            connection=connection,
            exc_handler=exc_handler,
            exception_handlers=exception_handlers,
            default_worker_ttl=settings.DEFAULT_WORKER_TTL,
            job_class=job_class,
            queue_class=queue_class,
            log_job_description=log_job_description,
            job_monitoring_interval=job_monitoring_interval,
            disable_default_exception_handler=disable_default_exception_handler,  # noqa: E501
            prepare_for_work=prepare_for_work,
            serializer=rq.serializers.JSONSerializer,
        )


# @redis_connect_retry()
def enqueue_delay(
    queue_name: str, job_id: str, delay: int, *args, **kwargs
) -> Job:
    """Enqueue a job to run after specific seconds."""
    scheduler = django_rq.get_scheduler(name=queue_name)
    return scheduler.enqueue_at(
        datetime.utcnow() + timedelta(seconds=delay),
        job_id=job_id,
        *args,
        **kwargs,
    )


# @redis_connect_retry()
def queue_cancel_job(queue_name: str, job_id: str) -> None:
    scheduler = django_rq.get_scheduler(name=queue_name)
    scheduler.cancel(job_id)


# @redis_connect_retry()
def unique_enqueue(queue_name: str, job_id: str, *args, **kwargs) -> Job:
    """Enqueue a new job if it is not already enqueued.

    Detects if a job with the same id is already enqueued and if it is
    it will return it instead of enqueuing a new one.
    """
    for name in settings.RQ_QUEUES:
        job = job_from_queue(name, job_id)
        if job:
            logger.info(
                f"Skip enqueing job: {job_id} because it is already enqueued"
            )
            return job

    queue = django_rq.get_queue(name=queue_name)
    kwargs["job_id"] = job_id
    logger.info(f"Enqueing unique job: {job_id}")
    return queue.enqueue(*args, **kwargs)


# @redis_connect_retry()
def job_from_queue(
    queue: typing.Union[Queue, str], job_id: str
) -> typing.Optional[Job]:
    """Return queue job if it not canceled or finished else None."""
    if type(queue) is str:
        queue = django_rq.get_queue(name=queue)
    job = queue.fetch_job(job_id)
    if job and job.get_status(refresh=True) in [
        rq.job.JobStatus.QUEUED,
        rq.job.JobStatus.STARTED,
        rq.job.JobStatus.DEFERRED,
        rq.job.JobStatus.SCHEDULED,
    ]:
        return job
    return None
