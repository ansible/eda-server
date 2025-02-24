import logging
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aap_eda.core"

    def ready(self):
        # make sure we apply DAB decorations in case they are not yet imported
        from aap_eda.api.views import dab_decorate  # noqa: F401

        # Run the startup logging for rq worker

        if "rqworker" in sys.argv:
            from aap_eda.utils.logging import startup_logging

            startup_logging(logger)
