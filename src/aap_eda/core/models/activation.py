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

from aap_eda.core.enums import RestartPolicy

from .base import CopyfyMixin, OIDField

__all__ = (
    "Activation",
    "ActivationInstance",
    "ActivationInstanceLog",
)


class Activation(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_activation"
        indexes = [models.Index(fields=["name"], name="ix_activation_name")]

    name = models.TextField(null=False)
    description = models.TextField()
    working_directory = models.TextField()
    execution_environment = models.TextField()
    rulebook_id = models.ForeignKey(
        "Rulebook", on_delete=models.CASCADE, null=False
    )
    inventory_id = models.ForeignKey(
        "Inventory", on_delete=models.CASCADE, null=False
    )
    extra_var_id = models.ForeignKey("ExtraVar", on_delete=models.CASCADE)
    restart_policy = models.TextField(
        choices=RestartPolicy.choices(),
        default=RestartPolicy.ON_FAILURE,
        null=False,
    )
    status = models.TextField()
    is_enabled = models.BooleanField(null=False, default=True)
    restarted_at = models.DateTimeField()
    restart_count = models.IntegerField(null=False, default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


# This table will have an pre-insert trigger that will
# set the large_data_id if it is null.
# This table will have a post-delete trigger that will
# cascade delete action to the large object table.
class ActivationInstance(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_activation_instance"
        indexes = [
            models.Index(fields=["name"], name="ix_act_inst_name"),
        ]

    name = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    rulebook = models.ForeignKey("Rulebook", on_delete=models.CASCADE)
    inventory = models.ForeignKey("Inventory", on_delete=models.CASCADE)
    extra_var = models.ForeignKey("ExtraVar", on_delete=models.CASCADE)
    working_directory = models.TextField()
    execution_environment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    large_data_id = OIDField(null=True)


class ActivationInstanceLog(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_activation_instance_log"

    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    line_number = models.IntegerField()
    log = models.TextField()
