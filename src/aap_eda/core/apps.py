#  Copyright 2025 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import logging
import sys

from dispatcherd.config import setup as dispatcher_setup
from django.apps import AppConfig
from django.conf import settings

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
        dispatcher_setup(settings.DISPATCHERD_DEFAULT_SETTINGS)
