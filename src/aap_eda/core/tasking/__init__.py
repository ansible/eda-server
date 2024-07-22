"""Tools for running background tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import MethodType
from typing import Any, Callable, Iterable, Optional, Protocol, Type, Union

import rq
import rq_scheduler
from django.conf import settings
from django_rq import enqueue, get_queue, get_scheduler, job
from django_rq.queues import Queue as _Queue
from rq import Connection, Worker as _Worker, results
from rq.defaults import (
    DEFAULT_JOB_MONITORING_INTERVAL,
    DEFAULT_RESULT_TTL,
    DEFAULT_WORKER_TTL,
)
from rq.job import Job as _Job, JobStatus
from rq.serializers import JSONSerializer

__all__ = [
    "Job",
    "Queue",
    "ActivationWorker",
    "DefaultWorker",
    "enqueue",
    "job",
    "get_queue",
    "unique_enqueue",
    "job_from_queue",
]

logger = logging.getLogger(__name__)

ErrorHandlerType = Callable[[_Job], None]

_ErrorHandlersArgType = Union[
    list[ErrorHandlerType],
    tuple[ErrorHandlerType],
    ErrorHandlerType,
    None,
]


def enable_redis_prefix():
    redis_prefix = settings.RQ_REDIS_PREFIX

    rq.worker_registration.REDIS_WORKER_KEYS = f"{redis_prefix}:workers"
    rq.worker_registration.WORKERS_BY_QUEUE_KEY = f"{redis_prefix}:workers:%s"
    rq.queue.Queue.redis_queue_namespace_prefix = f"{redis_prefix}:queue:"
    rq.queue.Queue.redis_queues_keys = f"{redis_prefix}:queues"
    rq.worker.Worker.redis_worker_namespace_prefix = f"{redis_prefix}:worker:"
    rq.worker.Worker.redis_workers_keys = f"{redis_prefix}:workers"
    rq.job.Job.redis_job_namespace_prefix = f"{redis_prefix}:job:"
    rq.registry.BaseRegistry.key_template = f"{redis_prefix}:registry:{0}"
    rq.registry.StartedJobRegistry.key_template = f"{redis_prefix}:wip:{0}"
    rq.registry.FinishedJobRegistry.key_template = (
        f"{redis_prefix}:finished:{0}"
    )
    rq.registry.FailedJobRegistry.key_template = f"{redis_prefix}:failed:{0}"
    rq.registry.DeferredJobRegistry.key_template = (
        f"{redis_prefix}:deferred:{0}"
    )
    rq.registry.ScheduledJobRegistry.key_template = (
        f"{redis_prefix}:scheduled:{0}"
    )
    rq.registry.CanceledJobRegistry.key_template = (
        f"{redis_prefix}:canceled:{0}"
    )

    rq_scheduler.Scheduler.redis_scheduler_namespace_prefix = (
        f"{redis_prefix}:scheduler_instance:"
    )
    rq_scheduler.Scheduler.scheduler_key = f"{redis_prefix}:scheduler"
    rq_scheduler.Scheduler.scheduler_lock_key = (
        f"{redis_prefix}:scheduler_lock"
    )
    rq_scheduler.Scheduler.scheduled_jobs_key = (
        f"{redis_prefix}:scheduler:scheduled_jobs"
    )

    def eda_get_key(job_id):
        return f"{redis_prefix}:results:{job_id}"

    results.get_key = eda_get_key

    def cls_get_key(cls, job_id):
        return f"{redis_prefix}:results:{job_id}"

    results.Result.get_key = MethodType(cls_get_key, results.Result)

    def property_registry_cleaning_key(self):
        return f"{redis_prefix}:clean_registries:{self.name}"

    setattr(  # noqa: B010
        rq.queue.Queue,
        "registry_cleaning_key",
        property(property_registry_cleaning_key),
    )


enable_redis_prefix()


class SerializerProtocol(Protocol):
    @staticmethod
    def dumps(obj: Any) -> bytes:
        ...

    @staticmethod
    def loads(data: bytes) -> Any:
        ...


class Queue(_Queue):
    """Custom queue class.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        name: str = "default",
        default_timeout: int = -1,
        connection: Optional[Connection] = None,
        is_async: bool = True,
        job_class: Optional[_Job] = None,
        serializer: Optional[SerializerProtocol] = None,
        **kwargs: Any,
    ):
        if serializer is None:
            serializer = JSONSerializer

        super().__init__(
            name=name,
            default_timeout=default_timeout,
            connection=connection,
            is_async=is_async,
            job_class=job_class,
            serializer=serializer,
            **kwargs,
        )


class Job(_Job):
    """Custom job class.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        id: Optional[str] = None,
        connection: Optional[Connection] = None,
        serializer: Optional[SerializerProtocol] = None,
    ):
        if serializer is None:
            serializer = JSONSerializer

        super().__init__(id, connection, serializer)


class DefaultWorker(_Worker):
    """Custom default worker class used for non-activation tasks.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        queues: Iterable[Union[Queue, str]],
        name: Optional[str] = "default",
        default_result_ttl: int = DEFAULT_RESULT_TTL,
        connection: Optional[Connection] = None,
        exc_handler: Any = None,
        exception_handlers: _ErrorHandlersArgType = None,
        default_worker_ttl: int = DEFAULT_WORKER_TTL,
        job_class: Type[_Job] = None,
        queue_class: Type[_Queue] = None,
        log_job_description: bool = True,
        job_monitoring_interval: int = DEFAULT_JOB_MONITORING_INTERVAL,
        disable_default_exception_handler: bool = False,
        prepare_for_work: bool = True,
        serializer: Optional[SerializerProtocol] = None,
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
            serializer=JSONSerializer,
        )


class ActivationWorker(_Worker):
    """Custom worker class used for activation related tasks.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        queues: Iterable[Union[Queue, str]],
        name: Optional[str] = "activation",
        default_result_ttl: int = DEFAULT_RESULT_TTL,
        connection: Optional[Connection] = None,
        exc_handler: Any = None,
        exception_handlers: _ErrorHandlersArgType = None,
        default_worker_ttl: int = DEFAULT_WORKER_TTL,
        job_class: Type[_Job] = None,
        queue_class: Type[_Queue] = None,
        log_job_description: bool = True,
        job_monitoring_interval: int = DEFAULT_JOB_MONITORING_INTERVAL,
        disable_default_exception_handler: bool = False,
        prepare_for_work: bool = True,
        serializer: Optional[SerializerProtocol] = None,
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
            serializer=JSONSerializer,
        )


def enqueue_delay(
    queue_name: str, job_id: str, delay: int, *args, **kwargs
) -> Job:
    """Enqueue a job to run after specific seconds."""
    scheduler = get_scheduler(name=queue_name)
    return scheduler.enqueue_at(
        datetime.utcnow() + timedelta(seconds=delay),
        job_id=job_id,
        *args,
        **kwargs,
    )


def queue_cancel_job(queue_name: str, job_id: str) -> None:
    scheduler = get_scheduler(name=queue_name)
    scheduler.cancel(job_id)


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

    queue = get_queue(name=queue_name)
    kwargs["job_id"] = job_id
    logger.info(f"Enqueing unique job: {job_id}")
    return queue.enqueue(*args, **kwargs)


def job_from_queue(queue: Union[Queue, str], job_id: str) -> Optional[Job]:
    """Return queue job if it not canceled or finished else None."""
    if type(queue) is str:
        queue = get_queue(name=queue)
    job = queue.fetch_job(job_id)
    if job and job.get_status(refresh=True) in [
        JobStatus.QUEUED,
        JobStatus.STARTED,
        JobStatus.DEFERRED,
        JobStatus.SCHEDULED,
    ]:
        return job
    return None
