import logging
import sys

from django.apps import AppConfig
from django.conf import settings
from flags.state import flag_enabled

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aap_eda.core"

    def ready(self):
        # make sure we apply DAB decorations in case they are not yet imported
        from aap_eda.api.views import dab_decorate  # noqa: F401

        # Run the startup logging for rq worker
        # WARNING: rqworker can run rq workers or dispatcherd workers
        if "rqworker" in sys.argv:
            from aap_eda.utils.logging import startup_logging

            startup_logging(logger)

        # Enable default dispatcher config. Workers may override this
        self.configure_dispatcher()

    def configure_dispatcher(self):
        """Configure dispatcher settings."""
        if flag_enabled(settings.DISPATCHERD_FEATURE_FLAG_NAME):
            from dispatcherd.config import setup as dispatcher_setup

            dispatcher_setup(settings.DISPATCHERD_DEFAULT_SETTINGS)
