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
"""
Django settings.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/

Quick-start development settings - unsuitable for production
See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

Common settings:

The following values can be defined as well as environment variables
with the prefix EDA_:

* SETTINGS_FILE - An path to file to load settings from
    Default: /etc/eda/settings.yaml
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


from aap_eda.settings import constants

DEBUG = False
ALLOWED_HOSTS = []
CSRF_TRUSTED_ORIGINS = []

# Session settings
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True

# JWT token lifetime
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = 60
JWT_REFRESH_TOKEN_LIFETIME_DAYS = 365

# Defines feature flags, and their conditions.
# See https://cfpb.github.io/django-flags/
FLAGS = {}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/
STATIC_URL = "static/"
STATIC_ROOT = "/var/lib/eda/static"

MEDIA_ROOT = "/var/lib/eda/files"

RENAMED_USERNAME_PREFIX = "eda_"

# ---------------------------------------------------------
# DEPLOYMENT SETTINGS
# ---------------------------------------------------------
DEPLOYMENT_TYPE = "podman"
WEBSOCKET_BASE_URL = "ws://localhost:8000"
WEBSOCKET_SSL_VERIFY = "yes"
WEBSOCKET_TOKEN_BASE_URL = None
PODMAN_SOCKET_URL = None
PODMAN_SOCKET_TIMEOUT = 0
PODMAN_MEM_LIMIT = "200m"
PODMAN_ENV_VARS = {}
PODMAN_MOUNTS = []
PODMAN_EXTRA_ARGS = {}
DEFAULT_PULL_POLICY = "Always"
CONTAINER_NAME_PREFIX = "eda"

MQ_UNIX_SOCKET_PATH = None
MQ_HOST = "localhost"
MQ_PORT = 6379
MQ_USER = None
MQ_USER_PASSWORD = None
MQ_CLIENT_CACERT_PATH = None
MQ_CLIENT_CERT_PATH = None
MQ_CLIENT_KEY_PATH = None
MQ_TLS = None
MQ_DB = constants.DEFAULT_REDIS_DB
RQ_REDIS_PREFIX = "eda-rq"


# The HA cluster hosts is a string of <host>:<port>[,<host>:port>]+
# and is exhaustive; i.e., not in addition to REDIS_HOST:REDIS_PORT.
# EDA does not validate the content, but relies on DAB to do so.
#
# In establishing an HA Cluster Redis client connection DAB ignores
# the host and port kwargs.
MQ_REDIS_HA_CLUSTER_HOSTS = ""

# A list of queues to be used in multinode mode
# If the list is empty, use the default singlenode queue name
RULEBOOK_WORKER_QUEUES = []

DEFAULT_QUEUE_TIMEOUT = 300
DEFAULT_RULEBOOK_QUEUE_TIMEOUT = 120

RULEBOOK_QUEUE_NAME = "activation"

API_PREFIX = "api/eda"

APP_LOG_LEVEL = "INFO"

SCHEDULER_JOB_INTERVAL = 5

# ---------------------------------------------------------
# CONTROLLER SETTINGS
# ---------------------------------------------------------
CONTROLLER_URL = "default_controller_url"
CONTROLLER_TOKEN = "default_controller_token"
CONTROLLER_SSL_VERIFY = "yes"

# ---------------------------------------------------------
# RULEBOOK LIVENESS SETTINGS
# ---------------------------------------------------------
RULEBOOK_READINESS_TIMEOUT_SECONDS = 60
RULEBOOK_LIVENESS_CHECK_SECONDS = 300
RULEBOOK_LIVENESS_TIMEOUT_SECONDS = 310
ACTIVATION_RESTART_SECONDS_ON_COMPLETE = 0
ACTIVATION_RESTART_SECONDS_ON_FAILURE = 60
ACTIVATION_MAX_RESTARTS_ON_FAILURE = 5

# -1 means no limit
MAX_RUNNING_ACTIVATIONS = 5

# ---------------------------------------------------------
# RULEBOOK ENGINE LOG LEVEL
# ---------------------------------------------------------
ANSIBLE_RULEBOOK_LOG_LEVEL = "error"
ANSIBLE_RULEBOOK_FLUSH_AFTER = 100

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE JWT SETTINGS
# ---------------------------------------------------------
ANSIBLE_BASE_JWT_VALIDATE_CERT = False
ANSIBLE_BASE_JWT_KEY = "https://localhost"

# These settings have defaults in DAB
# ALLOW_LOCAL_RESOURCE_MANAGEMENT (False)
# RESOURCE_SERVICE_PATH
# RESOURCE_SERVER_SYNC_ENABLED
# ENABLE_SERVICE_BACKED_SSO

ALLOW_LOCAL_ASSIGNING_JWT_ROLES = False
ALLOW_SHARED_RESOURCE_CUSTOM_ROLES = False

# --------------------------------------------------------
# DJANGO ANSIBLE BASE RESOURCE API CLIENT
# --------------------------------------------------------

RESOURCE_SERVER__URL = "https://localhost"
RESOURCE_SERVER__SECRET_KEY = ""
RESOURCE_SERVER__VALIDATE_HTTPS = False
RESOURCE_JWT_USER_ID = None

ANSIBLE_BASE_MANAGED_ROLE_REGISTRY = {}

ACTIVATION_DB_HOST = "host.containers.internal"
PG_NOTIFY_TEMPLATE_RULEBOOK = None
SAFE_PLUGINS_FOR_PORT_FORWARD = [
    "ansible.eda.webhook",
    "ansible.eda.alertmanager",
]
API_PATH_UI_PATH_MAP = {"/api/controller": "/execution", "/": "/#"}
PG_NOTIFY_DSN_SERVER = None
EVENT_STREAM_BASE_URL = None
EVENT_STREAM_MTLS_BASE_URL = None
MAX_PG_NOTIFY_MESSAGE_SIZE = 6144
