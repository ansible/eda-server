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

import yaml
from django.conf import settings

from aap_eda.api.exceptions import MissingListenerRulebook
from aap_eda.api.serializers import ActivationCreateSerializer
from aap_eda.core import models
from aap_eda.tasks.orchestrator import start_activation

logger = logging.getLogger(__name__)


class ListenerActivation:
    def __init__(self, source, request):
        self.source = source
        self.request = request

    def __call__(self):
        context = {"request": self.request}
        data = {}
        extra_var = models.ExtraVar.objects.create(
            extra_var=yaml.dump(self.source.listener_args)
        )

        rulebook = models.Rulebook.objects.filter(
            name=settings.PG_NOTIFY_TEMPLATE_RULEBOOK
        ).first()
        if not rulebook:
            logger.error(
                "Missing Listener rulebook %s",
                settings.PG_NOTIFY_TEMPLATE_RULEBOOK,
            )
            raise MissingListenerRulebook

        data["rulebook_id"] = rulebook.id

        data["extra_var_id"] = extra_var.id
        data["decision_environment_id"] = self.source.decision_environment_id
        data["name"] = f"{self.source.name}-listener"
        data[
            "description"
        ] = f"Listener Activation for source {self.source.name}"
        data["is_enabled"] = self.source.is_enabled
        data["sources"] = [self.source.id]
        data["listener"] = True
        serializer = ActivationCreateSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)

        logger.error(serializer.validated_data)
        response = serializer.create(serializer.validated_data)

        if response.is_enabled:
            start_activation(activation_id=response.id)
