import logging

from aap_eda.core.tasking import job

logger = logging.getLogger(__name__)


@job
def import_project():
    logger.info("[Task]: Import project")


@job
def sync_project():
    logger.info("[Task]: Sync project")
