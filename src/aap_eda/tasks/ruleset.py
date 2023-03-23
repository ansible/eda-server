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
from aap_eda.services.ruleset.activate_rulesets import ActivateRulesets

logger = logging.getLogger(__name__)


@job
def activate_rulesets(
    activation_id: int,
    execution_environment: str,
    deployment_type: str,
    host: str,
    port: int,
) -> None:
    logger.info(f"Task started: Activate ruleset ({activation_id=})")

    ActivateRulesets().activate(
        activation_id,
        execution_environment,
        deployment_type,
        host,
        port,
    )

    logger.info(f"Task finished: Ruleset ({activation_id}) is activated.")
