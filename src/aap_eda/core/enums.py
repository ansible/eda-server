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

from enum import Enum


class DjangoEnum(Enum):
    @classmethod
    def choices(cls):
        return tuple((e.value, e.value) for e in cls)

    @classmethod
    def values(cls):
        return tuple(e.value for e in cls)

    def __str__(self):
        return str(self.value)


# =======================================================================


class RestartPolicy(DjangoEnum):
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    NEVER = "never"


class ResourceType(DjangoEnum):
    ACTIVATION = "activation"
    ACTIVATION_INSTANCE = "activation_instance"
    AUDIT_RULE = "audit_rule"
    JOB = "job"
    TASK = "task"
    USER = "user"
    PROJECT = "project"
    INVENTORY = "inventory"
    EXTRA_VAR = "extra_var"
    PLAYBOOK = "playbook"
    RULEBOOK = "rulebook"
    EXECUTION_ENV = "execution_env"
    ROLE = "role"


class Action(DjangoEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class InventorySource(DjangoEnum):
    PROJECT = "project"
    COLLECTION = "collection"
    USER_DEFINED = "user_defined"
    EXECUTION_ENV = "execution_env"


class ActivationStatus(DjangoEnum):
    RUNNING = "running"
    PENDING = "pending"
    FAILED = "failed"
    STOPPED = "stopped"
    COMPLETED = "completed"


class EDADeployment(DjangoEnum):
    LOCAL = "local"
    DOCKER = "docker"
    PODMAN = "podman"
    # TODO: Add K8S support
