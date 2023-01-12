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
    "ActivationInstanceJobInstance",
    "JobInstanceEvent",
    "JobInstanceHost",
    "JobInstance",
    "Job",
)


class Job(models.Model):
    class Meta:
        db_table = "core_job"
        indexes = [models.Index(fields=["uuid"], name="ix_job_uuid")]

    uuid = models.UUIDField()


class JobInstance(models.Model):
    class Meta:
        db_table = "core_job_instance"
        indexes = [
            models.Index(fields=["name"], name="ix_job_instance_name"),
            models.Index(fields=["uuid"], name="ix_job_instance_uuid"),
        ]

    uuid = models.UUIDField()
    action = models.TextField()
    name = models.TextField()
    ruleset = models.TextField()
    rule = models.TextField()
    hosts = models.TextField()


class ActivationInstanceJobInstance(models.Model):
    class Meta:
        db_table = "core_activation_instance_job_instance"
        unique_together = ["activation_instance", "job_instance"]

    activation_instance = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    job_instance = models.ForeignKey("JobInstance", on_delete=models.CASCADE)


class JobInstanceEvent(models.Model):
    class Meta:
        db_table = "core_job_instance_event"
        indexes = [
            models.Index(
                fields=["job_uuid"], name="ix_job_instance_event_job_uuid"
            ),
        ]

    job_uuid = models.UUIDField()
    counter = models.IntegerField()
    stdout = models.TextField()
    type = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=False)


class JobInstanceHost(models.Model):
    class Meta:
        db_table = "core_job_instance_host"
        indexes = [
            models.Index(fields=["job_uuid"], name="ix_job_host_job_uuid"),
        ]

    job_uuid = models.UUIDField()
    playbook = models.TextField()
    play = models.TextField()
    task = models.TextField()
    status = models.TextField()
