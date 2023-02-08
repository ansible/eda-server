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
import subprocess

from redis import Redis
from rq import Queue, Worker

from aap_eda.core import models

logger = logging.getLogger(__name__)


def read_output(
    proc: subprocess.CompletedProcess, activation_instance_id: int
) -> None:
    redis = Redis()
    queue = Queue(connection=redis)
    task = queue.enqueue(
        insert_activation_instance_log_records, proc, activation_instance_id
    )
    worker = Worker([queue], connection=redis, name="read_output")
    worker.work(burst=True)

    logger.info(
        f"[Task {task.id}]: Read output from ({activation_instance_id})"
    )


def insert_activation_instance_log_records(
    proc: subprocess.CompletedProcess, activation_instance_id: int
) -> None:
    line_number = 0

    activation_instance_logs = []
    for line in proc.stdout.splitlines():
        activation_instance_log = models.ActivationInstanceLog(
            line_number=line_number,
            log=line,
            activation_instance_id=activation_instance_id,
        )
        activation_instance_logs.append(activation_instance_log)

        line_number += 1

    models.ActivationInstanceLog.objects.bulk_create(activation_instance_logs)

    logger.info(f"{line_number} of activation instance log are created.")
