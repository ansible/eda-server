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

import contextvars
import logging

log_tracking_id_var = contextvars.ContextVar("log_tracking_id")


class LogTrackingIdFilter(logging.Filter):
    def filter(self, record):
        record.log_tracking_id = log_tracking_id_var.get(
            "Log tracking id not set"
        )

        return True


def assign_log_tracking_id(log_tracking_id):
    log_tracking_id_var.set(log_tracking_id)
