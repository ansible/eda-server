"""Tools for running background tasks."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Protocol, Type, Union

from django_rq import enqueue, get_queue, job
from rq import Connection, Queue as _Queue, Worker as _Worker
from rq.defaults import (
    DEFAULT_JOB_MONITORING_INTERVAL,
    DEFAULT_RESULT_TTL,
    DEFAULT_WORKER_TTL,
)
from rq.job import Job as _Job
from rq.serializers import JSONSerializer

__all__ = ["Job", "Queue", "Worker", "enqueue", "job", "get_queue"]

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
        default_timeout: Union[int, str, None] = None,
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


class Worker(_Worker):
    """Custom worker class.

    Uses JSONSerializer as a default one.
    """

    def __init__(
        self,
        queues: Iterable[Union[Queue, str]],
        name: Optional[str] = None,
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
        if serializer is None:
            serializer = JSONSerializer

        super().__init__(
            queues,
            name,
            default_result_ttl,
            connection,
            exc_handler,
            exception_handlers,
            default_worker_ttl,
            job_class,
            queue_class,
            log_job_description,
            job_monitoring_interval,
            disable_default_exception_handler,
            prepare_for_work,
            serializer,
        )
