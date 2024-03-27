"""Tools for running background tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Optional, Protocol, Type, Union

from django.conf import settings
from django_rq import enqueue, get_queue, get_scheduler, job
from django_rq.queues import Queue as _Queue
from django_rq.settings import QUEUES
from redis import Redis
from rq import Connection, Worker as _Worker
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

        queues = [Queue(name="activation", connection=connection)]
        if settings.LOCAL_QUEUE_NAME:
            queues.append(
                Queue(name=settings.LOCAL_QUEUE_NAME, connection=connection)
            )

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


def enqueue_delay(queue_name: str, delay: int, *args, **kwargs) -> Job:
    """Enqueue a job to run after specific seconds."""
    scheduler = get_scheduler(name=queue_name)
    return scheduler.enqueue_at(
        datetime.utcnow() + timedelta(seconds=delay), *args, **kwargs
    )


def unique_enqueue(queue_name: str, job_id: str, *args, **kwargs) -> Job:
    try:
        return _unique_enqueue(queue_name, job_id, *args, **kwargs)
    except KeyError:
        if settings.REFRESH_RQ_QUEUES:
            logger.info(f"Missing queue {queue_name} will attempt to refresh")
            _refresh_queues()
            return _unique_enqueue(queue_name, job_id, *args, **kwargs)
        else:
            raise


def _refresh_queues():
    activation_values = QUEUES["activation"]
    redis = Redis(
        host=activation_values["HOST"], port=activation_values["PORT"]
    )
    queues = []
    for worker in _Worker.all(connection=redis):
        for queue in worker.queues:
            if queue.name not in queues:
                queues.append(queue.name)

    for queue in queues:
        if queue not in QUEUES:
            logger.info(f"Adding queue {queue} to RQ_QUEUES")
            QUEUES[queue] = activation_values


def _unique_enqueue(queue_name: str, job_id: str, *args, **kwargs) -> Job:
    """Enqueue a new job if it is not already enqueued.

    Detects if a job with the same id is already enqueued and if it is
    it will return it instead of enqueuing a new one.
    """
    queue = get_queue(queue_name)
    job = job_from_queue(queue, job_id)
    if job:
        logger.info(
            f"Skip enqueing job: {job_id} because it is already enqueued"
        )
        return job
    else:
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
