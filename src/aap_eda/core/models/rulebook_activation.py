#  Copyright 2022 Red Hat, Inc.
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

from django.db import models

from .activation import Activation
from .source import Source


class RulebookActivation(Activation):
    class Meta:
        db_table = "core_rulebook_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]
        ordering = ("-created_at",)

    sources = models.ManyToManyField(
        Source,
        default=None,
    )

    # TODO: we can move here other fields only related with Rulebook
    # activation like extra_vars and ruleset_stats, that would require
    # to change other pieces of code like the manager and the serializer.
