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

from aap_eda.core import models
from aap_eda.core.tasking import job
from aap_eda.services.ruleset.ansible_rulebook import AnsibleRulebookService

logger = logging.getLogger(__name__)


@job
def activate_rulesets(url: str, activation_id: str):
    logger.info(f"Task started: Activate ruleset ( {url=} {activation_id=} )")

    proc = AnsibleRulebookService().run(
        url=url,
        activation_id=activation_id,
    )

    line_number = 0

    activation_instance_logs = []
    for line in proc.stdout.splitlines():
        activation_instance_log = models.ActivationInstanceLog(
            line_number=line_number,
            log=line,
            activation_id=activation_id,
        )
        activation_instance_logs.append(activation_instance_log)

        line_number += 1

    models.ActivationInstanceLog.objects.bulk_create(activation_instance_logs)
    logger.info(f"{line_number} of activation instance log are created.")

    logger.info(f"Task finished: Ruleset for ({activation_id}) is activated.")
