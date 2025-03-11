"""Tools for running background tasks."""
import logging

from django.conf import settings

from dispatcher.factories import get_control_from_settings


logger = logging.getLogger(__name__)


def enqueue_delay(
    queue_name: str, job_id: str, delay: int, method, *args, **kwargs
) -> None:
    """Enqueue a job to run after specific seconds."""
    method.apply_async(
        args=args, kwargs=kwargs, queue=queue_name, delay=delay, uuid=job_id
    )


def queue_cancel_job(queue_name: str, job_id: str) -> None:
    ctl = get_control_from_settings(default_publish_channel=queue_name)
    canceled_data = ctl.control_with_reply("cancel", data={"uuid": job_id})
    if canceled_data:
        logger.warning(f"Canceled jobs in flight: {canceled_data}")
    else:
        logger.debug(f"No jobs running with id {job_id} to cancel")
