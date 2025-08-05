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
"""
Django settings.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/

Quick-start development settings - unsuitable for production
See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/


All settings can be overwritten via environment variables or setting files
should be listed in this file with type hints and default values.

Common settings:

The following values can be defined as well as environment variables
with the prefix EDA_:

* SECRET_KEY - A Django secret key.
* SECRET_KEY_FILE - A file path to load Django secret key from.
    Example:
      export SECRET_KEY_FILE=/etc/eda
* DEBUG
* ALLOWED_HOSTS - A list of allowed hostnames or
    a comma separated string.
    Ex: export EDA_ALLOWED_HOSTS="localhost,127.0.0.1"
    Ex: export EDA_ALLOWED_HOSTS='["localhost", "127.0.0.1"]'
* SESSION_COOKIE_AGE - Session cookie expiration time

Database settings:

* DB_HOST - Database hostname (default: "127.0.0.1")
* DB_PORT - Database port (default: 5432)
* DB_USER - Database username (default: "postgres")
* DB_PASSWORD - Database user password (default: None)
* DB_NAME - Database name (default: "eda")
* EDA_PGSSLMODE - SSL mode for PostgreSQL connection (default: "prefer")
* EDA_PGSSLCERT - Path to SSL certificate file (default: "")
* EDA_PGSSLKEY - Path to SSL key file (default: "")
* EDA_PGSSLROOTCERT - Path to SSL root certificate file (default: "")

Optionally you can define DATABASES as an object
* DATABASES - A dict with django database settings


Redis queue settings:

* MQ_UNIX_SOCKET_PATH - Redis unix socket path (default: None)
*   - Takes precedence over host and port
* MQ_HOST - Redis queue hostname (default: "127.0.0.1")
* MQ_PORT - Redis queue port (default: 6379)
* MQ_TLS - Force TLS on when True (default: None)
* MQ_DB - Redis queue database (default: 0)
* MQ_USER - Redis user (default: None)
* MQ_USER_PASSWORD - Redis user passed (default: None)
* MQ_CLIENT_CERT_PATH - Redis TLS client certificate path (default: None)
*   - If MQ_UNIX_SOCKET_PATH is not set and MQ_CLIENT_CERT_PATH
*     is set TLS with be used.
* MQ_CLIENT_KEY_PATH - Redis TLS client key path (default: None)
* MQ_CLIENT_CACERT_PATH - Redis TLS CA certificate path (default: None)


Podman settings:
PODMAN_MOUNTS - A list of dicts with mount options. Each dict must contain
    the following keys: source, target, type.
    Look at https://docs.podman.io/en/v4.4/markdown/options/mount.html
    for more information.
    Example:
      export PODMAN_MOUNTS='@json [{"source": "/var/run/containers/storage",
                             "target": "/var/run/containers/storage",
                             "type": "bind"}]'


Django Ansible Base settings:
To configure a Resource Server for syncing of managed resources:
* RESOURCE_SERVER__URL - The URL to connect to the resource server
* RESOURCE_SERVER__SECRET_KEY - The secret key needed to pull the resource list
* RESOURCE_SERVER__VALIDATE_HTTPS - Whether to validate https, default to False
* ANSIBLE_BASE_MANAGED_ROLE_REGISTRY - Syncing of the Platform Auditor role

"""

from typing import NewType, Optional, Union

from aap_eda.settings import core

StrToList = NewType("StrToList", Union[list, str])
UrlSlash = NewType("UrlSlash", Optional[str])


DEBUG: bool = False
ALLOWED_HOSTS: StrToList = []

# A list or a comma separated string of allowed origins for CSRF protection
# in the form of [scheme://]host[:port]. Supports wildcards.
# More info: https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-trusted-origins  # noqa: E501
CSRF_TRUSTED_ORIGINS: StrToList = []

# Session settings
SESSION_COOKIE_AGE: int = 1800
SESSION_SAVE_EVERY_REQUEST: bool = True

# JWT token lifetime
JWT_ACCESS_TOKEN_LIFETIME_MINUTES: int = 60
JWT_REFRESH_TOKEN_LIFETIME_DAYS: int = 365

# Defines feature flags, and their conditions.
# See https://cfpb.github.io/django-flags/
FLAGS: dict = {}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/
STATIC_URL: str = "static/"
STATIC_ROOT: str = "/var/lib/eda/static"

MEDIA_ROOT: str = "/var/lib/eda/files"

RENAMED_USERNAME_PREFIX: str = "eda_"

# ---------------------------------------------------------
# DEPLOYMENT SETTINGS
# ---------------------------------------------------------
DEPLOYMENT_TYPE: str = "podman"
WEBSOCKET_BASE_URL: str = "ws://localhost:8000"
WEBSOCKET_SSL_VERIFY: Union[bool, str] = "yes"
WEBSOCKET_TOKEN_BASE_URL: Optional[str] = None
PODMAN_SOCKET_URL: Optional[str] = None
PODMAN_SOCKET_TIMEOUT: Optional[int] = 0
PODMAN_MEM_LIMIT: Optional[str] = "200m"
PODMAN_ENV_VARS: Optional[dict] = {}
PODMAN_MOUNTS: Optional[list] = []
PODMAN_EXTRA_ARGS: Optional[dict] = {}
DEFAULT_PULL_POLICY: str = "Always"
CONTAINER_NAME_PREFIX: str = "eda"

RQ_REDIS_PREFIX: str = "eda-rq"
MQ_UNIX_SOCKET_PATH: Optional[str] = None
MQ_HOST: str = "localhost"
MQ_PORT: int = 6379
MQ_USER: Optional[str] = None
MQ_USER_PASSWORD: Optional[str] = None
MQ_CLIENT_CACERT_PATH: Optional[str] = None
MQ_CLIENT_CERT_PATH: Optional[str] = None
MQ_CLIENT_KEY_PATH: Optional[str] = None
MQ_TLS: Optional[str] = None
MQ_DB: int = core.DEFAULT_REDIS_DB

# The HA cluster hosts is a string of <host>:<port>[,<host>:port>]+
# and is exhaustive; i.e., not in addition to REDIS_HOST:REDIS_PORT.
# EDA does not validate the content, but relies on DAB to do so.
#
# In establishing an HA Cluster Redis client connection DAB ignores
# the host and port kwargs.
MQ_REDIS_HA_CLUSTER_HOSTS: str = ""
MQ_SOCKET_KEEP_ALIVE: bool = True
MQ_SOCKET_CONNECT_TIMEOUT: int = 10
MQ_SOCKET_TIMEOUT: int = 150
MQ_CLUSTER_ERROR_RETRY_ATTEMPTS: int = 3

# A list of queues to be used in multinode mode
# If the list is empty, use the default singlenode queue name
RULEBOOK_WORKER_QUEUES: StrToList = []

DEFAULT_QUEUE_TIMEOUT: int = 300
DEFAULT_RULEBOOK_QUEUE_TIMEOUT: int = 120

RULEBOOK_QUEUE_NAME: str = "activation"

API_PREFIX: str = "api/eda"

APP_LOG_LEVEL: str = "INFO"

SCHEDULER_JOB_INTERVAL: int = 5

# ---------------------------------------------------------
# CONTROLLER SETTINGS
# ---------------------------------------------------------
CONTROLLER_URL: str = "default_controller_url"
CONTROLLER_TOKEN: str = "default_controller_token"
CONTROLLER_SSL_VERIFY: Union[bool, str] = "yes"

# ---------------------------------------------------------
# RULEBOOK LIVENESS SETTINGS
# ---------------------------------------------------------
RULEBOOK_READINESS_TIMEOUT_SECONDS: int = 60
RULEBOOK_LIVENESS_CHECK_SECONDS: int = 300
RULEBOOK_LIVENESS_TIMEOUT_SECONDS: int = 310
ACTIVATION_RESTART_SECONDS_ON_COMPLETE: int = 0
ACTIVATION_RESTART_SECONDS_ON_FAILURE: int = 60
ACTIVATION_MAX_RESTARTS_ON_FAILURE: int = 5

# ---------------------------------------------------------
# RULEBOOK ENGINE LOG LEVEL
# ---------------------------------------------------------
ANSIBLE_RULEBOOK_LOG_LEVEL: str = "error"
ANSIBLE_RULEBOOK_FLUSH_AFTER: int = 100

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE JWT SETTINGS
# ---------------------------------------------------------
ANSIBLE_BASE_JWT_VALIDATE_CERT: bool = False
ANSIBLE_BASE_JWT_KEY: str = "https://localhost"

# Default Not allow local resource management.
# Ignore what is set in DAB.
# Can be changed via ENV
ALLOW_LOCAL_RESOURCE_MANAGEMENT: bool = False

# These settings have defaults in DAB
# RESOURCE_SERVICE_PATH
# RESOURCE_SERVER_SYNC_ENABLED
# ENABLE_SERVICE_BACKED_SSO

ALLOW_LOCAL_ASSIGNING_JWT_ROLES: bool = False
ALLOW_SHARED_RESOURCE_CUSTOM_ROLES: bool = False

# --------------------------------------------------------
# DJANGO ANSIBLE BASE RESOURCE API CLIENT
# --------------------------------------------------------

RESOURCE_SERVER__URL: Optional[str] = "https://localhost"
RESOURCE_SERVER__SECRET_KEY: Optional[str] = ""
RESOURCE_SERVER__VALIDATE_HTTPS: bool = False
RESOURCE_JWT_USER_ID: Optional[str] = None

# The preload data scrip is used instead of the DAB managed role creator
ANSIBLE_BASE_MANAGED_ROLE_REGISTRY: dict = {}

ACTIVATION_DB_HOST: str = "host.containers.internal"
PG_NOTIFY_TEMPLATE_RULEBOOK: Optional[str] = None
SAFE_PLUGINS_FOR_PORT_FORWARD: list = [
    "ansible.eda.webhook",
    "ansible.eda.alertmanager",
]
API_PATH_UI_PATH_MAP: dict = {"/api/controller": "/execution", "/": "/#"}
PG_NOTIFY_DSN_SERVER: Optional[str] = None
EVENT_STREAM_BASE_URL: UrlSlash = None
EVENT_STREAM_MTLS_BASE_URL: UrlSlash = None
MAX_PG_NOTIFY_MESSAGE_SIZE: int = 6144

# --------------------------------------------------------
# METRICS COLLECTIONS:
# --------------------------------------------------------
AUTOMATION_ANALYTICS_URL: str = (
    "https://cloud.redhat.com/api/ingress/v1/upload"
)
AUTOMATION_ANALYTICS_OIDC_TOKEN_URL: str = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"  # noqa: E501
ANALYTICS_PROXY_URL: Optional[str] = None
INSIGHTS_CERT_PATH: str = "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
AUTOMATION_AUTH_METHOD: str = "service-account"
INSIGHTS_TRACKING_STATE: bool = False
AUTOMATION_ANALYTICS_GATHER_INTERVAL: int = 14400
REDHAT_USERNAME: str = ""
REDHAT_PASSWORD: str = ""
