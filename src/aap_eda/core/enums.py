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


# TODO(alex): migrate to django.db.models.TextChoices
class DjangoStrEnum(str, Enum):
    @classmethod
    def choices(cls):
        return tuple((e.value, e.value) for e in cls)

    @classmethod
    def values(cls):
        return tuple(e.value for e in cls)

    def __str__(self):
        return str(self.value)


# =======================================================================


class RestartPolicy(DjangoStrEnum):
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    NEVER = "never"


class ResourceType(DjangoStrEnum):
    ACTIVATION = "activation"
    ACTIVATION_INSTANCE = "activation_instance"
    AUDIT_RULE = "audit_rule"
    USER = "user"
    PROJECT = "project"
    RULEBOOK = "rulebook"
    ROLE = "role"
    DECISION_ENVIRONMENT = "decision_environment"
    CREDENTIAL = "credential"
    CREDENTIAL_TYPE = "credential_type"
    EDA_CREDENTIAL = "eda_credential"
    EVENT_STREAM = "event_stream"
    ORGANIZATION = "organization"
    TEAM = "team"
    WEBHOOK = "webhook"


class Action(DjangoStrEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ENABLE = "enable"
    DISABLE = "disable"
    RESTART = "restart"
    SYNC = "sync"


# TODO: rename to "RulebookProcessStatus" or "ParentProcessStatus"
class ActivationStatus(DjangoStrEnum):
    STARTING = "starting"
    RUNNING = "running"
    PENDING = "pending"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DELETING = "deleting"
    COMPLETED = "completed"
    # TODO: unresponsive status is no longer necessary
    # monitor task will handle it
    UNRESPONSIVE = "unresponsive"
    ERROR = "error"
    WORKERS_OFFLINE = "workers offline"


# TODO: Deprecated, will be removed in future version, use
# DefaultCredentialType instead
class CredentialType(DjangoStrEnum):
    REGISTRY = "Container Registry"
    GITHUB = "GitHub Personal Access Token"
    GITLAB = "GitLab Personal Access Token"
    VAULT = "Vault"


class DefaultCredentialType(DjangoStrEnum):
    REGISTRY = "Container Registry"
    VAULT = "Vault"
    SOURCE_CONTROL = "Source Control"
    AAP = "Red Hat Ansible Automation Platform"
    GPG = "GPG Public Key"


# TODO: rename to "RulebookProcessStatus" or "ParentProcessStatus"
ACTIVATION_STATUS_MESSAGE_MAP = {
    ActivationStatus.PENDING: "Wait for a worker to be available to start activation",  # noqa: E501
    ActivationStatus.STARTING: "Worker is starting activation",
    ActivationStatus.RUNNING: "Container running activation",
    ActivationStatus.STOPPING: "Activation is being disabled",
    ActivationStatus.DELETING: "Activation is being deleted",
    ActivationStatus.COMPLETED: "Activation has completed",
    ActivationStatus.FAILED: "Activation has failed",
    ActivationStatus.STOPPED: "Activation has stopped",
    ActivationStatus.UNRESPONSIVE: "Activation is not responsive",
    ActivationStatus.ERROR: "Activation is in an error state",
    ActivationStatus.WORKERS_OFFLINE: "All workers in the node are offline",
}


# TODO: rename to "RulebookProcessRequest"
class ActivationRequest(DjangoStrEnum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    DELETE = "delete"
    AUTO_START = "auto_start"


class ProcessParentType(DjangoStrEnum):
    """Types of parent objects for a rulebook process."""

    ACTIVATION = "activation"
    EVENT_STREAM = "event_stream"


class RulebookProcessLogLevel(DjangoStrEnum):
    """Types of log levels for a rulebook process."""

    DEBUG = "debug"
    INFO = "info"
    ERROR = "error"


class WebhookAuthType(DjangoStrEnum):
    """Types of authentication for Webhook."""

    HMAC = "hmac"
    TOKEN = "token"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    OAUTH2JWT = "oauth2-jwt"
    ECDSA = "ecdsa"
    MTLS = "mtls"


class SignatureEncodingType(DjangoStrEnum):
    """Types of format for HMAC."""

    BASE64 = "base64"
    HEX = "hex"


class WebhookCredentialType(DjangoStrEnum):
    HMAC = "HMAC Webhook"
    BASIC = "Basic Webhook"
    TOKEN = "Token Webhook"
    OAUTH2 = "Oauth2 Webhook"
    OAUTH2_JWT = "Oauth2 JWT Webhook"
    ECDSA = "ECDSA Webhook"
    MTLS = "mTLS Webhook"


class CustomWebhookCredentialType(DjangoStrEnum):
    GITLAB = "GITLAB Webhook"
    GITHUB = "GitHub Webhook"
    SNOW = "Service Now Webhook"
    DYNATRACE = "Dynatrace Webhook"
