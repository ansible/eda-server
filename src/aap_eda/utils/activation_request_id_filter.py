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

activation_request_id_var = contextvars.ContextVar("request_id")


class ActivationRequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = activation_request_id_var.get(
            "activation request id not found"
        )

        return True


def assign_request_id_activation(request_id):
    activation_request_id_var.set(request_id)
