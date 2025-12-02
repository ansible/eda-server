"""Tools for running background tasks."""
from __future__ import annotations

import logging

from dispatcherd.factories import get_control_from_settings
from dispatcherd.processors.delayer import Delayer
from dispatcherd.publish import submit_task

from aap_eda import utils

__all__ = [
    "enqueue_delay",
    "queue_cancel_job",
    "unique_enqueue",
]

logger = logging.getLogger(__name__)


def enqueue_delay(
    queue_name: str, job_id: str, delay: int, *args, **kwargs
) -> None:
    """Enqueue a job to run after specific seconds in dispatcherd."""
    fn = args[0]
    args = tuple(args[1:])

    submit_task(
        fn,
        args=args,
        kwargs=kwargs,
        queue=utils.sanitize_postgres_identifier(queue_name),
        uuid=job_id,
        processor_options=[Delayer.Params(delay=delay)],
    )


def queue_cancel_job(queue_name: str, job_id: str) -> None:
    """Cancel a job in the queue using dispatcherd."""
    ctl = get_control_from_settings(default_publish_channel=queue_name)
    canceled_data = ctl.control_with_reply("cancel", data={"uuid": job_id})
    if canceled_data:
        logger.warning(f"Canceled jobs in flight: {canceled_data}")
    else:
        logger.debug(f"No jobs running with id {job_id} to cancel")


def unique_enqueue(queue_name: str, job_id: str, *args, **kwargs) -> None:
    """Enqueue a new job using dispatcherd.

    Note: Uniqueness is not guaranteed in dispatcherd, job is simply enqueued.
    """
    fn = args[0]
    args = tuple(args[1:])

    submit_task(
        fn,
        args=args,
        kwargs=kwargs,
        queue=utils.sanitize_postgres_identifier(queue_name),
        uuid=job_id,
    )
