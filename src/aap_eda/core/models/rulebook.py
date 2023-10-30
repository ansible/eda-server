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

__all__ = (
    "Rulebook",
    "Ruleset",
    "Rule",
    "AuditRule",
)


class Rulebook(models.Model):
    class Meta:
        db_table = "core_rulebook"
        unique_together = ["project_id", "name"]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(name=""),
                name="ck_rulebook_name_not_empty",
            ),
        ]

    name = models.TextField(null=False)
    description = models.TextField(null=True, default="")
    rulesets = models.TextField(null=False, default="")
    project = models.ForeignKey("Project", on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class Ruleset(models.Model):
    class Meta:
        db_table = "core_ruleset"
        unique_together = ["rulebook_id", "name"]

    name = models.TextField(null=False)
    sources = models.JSONField(default=dict)
    rulebook = models.ForeignKey("Rulebook", on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)


class Rule(models.Model):
    class Meta:
        db_table = "core_rule"
        unique_together = ["ruleset", "name"]

    ruleset = models.ForeignKey("Ruleset", on_delete=models.CASCADE, null=True)
    name = models.TextField(null=False)
    action = models.JSONField(default=dict, null=False)


class AuditRule(models.Model):
    class Meta:
        db_table = "core_audit_rule"
        indexes = [
            models.Index(fields=["name"], name="ix_audit_rule_name"),
            models.Index(fields=["fired_at"], name="ix_audit_rule_fired_at"),
        ]
        ordering = ("-fired_at",)

    name = models.TextField(null=False)
    status = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    fired_at = models.DateTimeField(null=False)
    rule_uuid = models.UUIDField(null=True)
    ruleset_uuid = models.UUIDField(null=True)
    ruleset_name = models.TextField(null=True)
    activation_instance = models.ForeignKey("ActivationInstance", on_delete=models.SET_NULL, null=True)
    job_instance = models.ForeignKey("JobInstance", on_delete=models.SET_NULL, null=True)


class AuditAction(models.Model):
    class Meta:
        db_table = "core_audit_action"
        unique_together = ["id", "name"]
        ordering = ("-fired_at", "-rule_fired_at")

    id = models.UUIDField(primary_key=True)
    name = models.TextField()
    status = models.TextField(blank=True)
    url = models.URLField(blank=True)
    fired_at = models.DateTimeField()
    rule_fired_at = models.DateTimeField(null=True)

    audit_rule = models.ForeignKey("AuditRule", on_delete=models.CASCADE, null=True)


class AuditEvent(models.Model):
    class Meta:
        db_table = "core_audit_event"
        ordering = ("-received_at", "-rule_fired_at")

    id = models.UUIDField(primary_key=True)
    source_name = models.TextField()
    source_type = models.TextField()
    received_at = models.DateTimeField()
    payload = models.JSONField(null=True)
    rule_fired_at = models.DateTimeField(null=True)

    audit_actions = models.ManyToManyField("AuditAction", related_name="audit_events")
