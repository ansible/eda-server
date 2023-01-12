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

from .base import CopyfyMixin

__all__ = (
    "Rulebook",
    "Ruleset",
    "Rule",
    "AuditRule",
)


class Rulebook(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_rulebook"
        unique_together = ["project_id", "name"]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_rulebook_name_not_empty",
                violation_error_message="Rulebook name must not be empty.",
            ),
        ]

    name = models.TextField(null=False)
    description = models.TextField(null=True, default="")
    rulesets = models.TextField(null=True)
    project = models.ForeignKey("Project", on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class Ruleset(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_ruleset"
        unique_together = ["rulebook_id", "name"]

    name = models.TextField(null=False)
    sources = models.JSONField(default=dict)
    rulebook = models.ForeignKey(
        "Rulebook", on_delete=models.CASCADE, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class Rule(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_rule"
        unique_together = ["ruleset", "name"]

    ruleset = models.ForeignKey("Ruleset", on_delete=models.CASCADE, null=True)
    name = models.TextField(null=False)
    action = models.JSONField(default=dict, null=False)


class AuditRule(models.Model, CopyfyMixin):
    class Meta:
        db_table = "core_audit_rule"
        indexes = [
            models.Index(fields=["name"], name="ix_audit_rule_name"),
            models.Index(
                fields=["fired_date"], name="ix_audit_rule_fired_date"
            ),
        ]

    name = models.TextField(null=False)
    description = models.TextField()
    status = models.TextField()
    fired_date = models.DateTimeField(null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    rule_id = models.ForeignKey("Rule", on_delete=models.CASCADE, null=True)
    ruleset = models.ForeignKey("Ruleset", on_delete=models.CASCADE, null=True)
    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE, null=True
    )
    job_instance = models.ForeignKey(
        "JobInstance", on_delete=models.CASCADE, null=True
    )
    definition = models.JSONField(null=False)
