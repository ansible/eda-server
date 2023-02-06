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

from aap_eda.core.enums import InventorySource

__all__ = "Inventory"


class Inventory(models.Model):
    class Meta:
        db_table = "core_inventory"
        constraints = [
            models.CheckConstraint(
                check=models.Q(inventory_source__in=InventorySource.values()),
                name="ck_inventory_source_values",
                violation_error_message=(
                    "Value not defined in Inventory Source enum."
                ),
            ),
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_empty_inventory_name",
                violation_error_message="Inventory name cannot be empty.",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inventory_source"], name="ix_inventory_inv_src"
            ),
        ]

    name = models.TextField(null=False)
    description = models.TextField(null=True, default="")
    inventory = models.TextField(null=True)
    inventory_source = models.TextField(
        choices=InventorySource.choices(), null=False
    )
    project = models.ForeignKey("Project", on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    @property
    def content(self):
        return self.inventory
