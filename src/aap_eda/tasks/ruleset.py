#  Copyright 2023 Red Hat, Inc.
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

from aap_eda.core.tasking import job
from aap_eda.services.activation import ActivationExecution

logger = logging.getLogger(__name__)


@job
def activate_rulesets(
    execution: ActivationExecution,
) -> None:
    logger.info(f"Task started: Activate ruleset ({execution.activation.id})")

    execution.activate()

    logger.info(
        f"Task finished: Ruleset ({execution.activation.id}) is activated."
    )
