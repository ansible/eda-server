#  Copyright 2024 Red Hat, Inc.
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

from ansible_base.resource_registry.tasks.sync import SyncExecutor
from django.conf import settings

logger = logging.getLogger(__name__)


# Started by the scheduler
def resync_shared_resources():
    try:
        SyncExecutor().run()
    except Exception as e:
        logger.error(
            f"Failed to sync shared resources. Error: {e}",
            exc_info=settings.DEBUG,
        )
