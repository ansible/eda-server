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
import os
from datetime import timedelta

import dynaconf
from django.core.exceptions import ImproperlyConfigured
from split_settings.tools import include

from aap_eda import utils
from aap_eda.core.enums import RulebookProcessLogLevel

default_settings_file = "/etc/eda/settings.yaml"

settings = dynaconf.Dynaconf(
    envvar="EDA_SETTINGS_FILE",
    envvar_prefix="EDA",
    settings_file=default_settings_file,
)


# ---------------------------------------------------------
# DJANGO SETTINGS
# ---------------------------------------------------------
def _get_secret_key() -> str:
    secret_key = settings.get("SECRET_KEY")
    secret_key_file = settings.get("SECRET_KEY_FILE")
    if secret_key and secret_key_file:
        raise ImproperlyConfigured(
            'Settings parameters "SECRET_KEY" and "SECRET_KEY_FILE"'
            " are mutually exclusive."
        )
    if secret_key:
        return secret_key
    if secret_key_file:
        with open(secret_key_file) as fp:
            return fp.read().strip()
    raise ImproperlyConfigured(
        'Either "SECRET_KEY" or "SECRET_KEY_FILE" settings'
        " parameters must be set."
    )


SECRET_KEY = _get_secret_key()


def _get_boolean(name: str, default=False) -> bool:
    value = settings.get(name, default)
    if isinstance(value, str):
        value = utils.str_to_bool(value)
    if not isinstance(value, bool):
        raise ImproperlyConfigured("{name} setting must be a boolean value.")
    return value


DEBUG = _get_boolean("DEBUG")

ALLOWED_HOSTS = settings.get("ALLOWED_HOSTS", [])
ALLOWED_HOSTS = (
    ALLOWED_HOSTS.split(",")
    if isinstance(ALLOWED_HOSTS, str)
    else ALLOWED_HOSTS
)
# A list or a comma separated string of allowed origins for CSRF protection
# in the form of [scheme://]host[:port]. Supports wildcards.
# More info: https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-trusted-origins  # noqa: E501
CSRF_TRUSTED_ORIGINS = settings.get("CSRF_TRUSTED_ORIGINS", [])
CSRF_TRUSTED_ORIGINS = (
    CSRF_TRUSTED_ORIGINS.split(",")
    if isinstance(CSRF_TRUSTED_ORIGINS, str)
    else CSRF_TRUSTED_ORIGINS
)

# Session settings
SESSION_COOKIE_AGE = settings.get("SESSION_COOKIE_AGE", 1800)
SESSION_SAVE_EVERY_REQUEST = True

# JWT token lifetime
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = settings.get(
    "JWT_ACCESS_TOKEN_LIFETIME_MINUTES",
    60,
)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = settings.get(
    "JWT_REFRESH_TOKEN_LIFETIME_DAYS",
    365,
)

# Application definition
INSTALLED_APPS = [
    "daphne",
    "flags",
    # Django apps
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "drf_spectacular",
    "django_rq",
    "django_filters",
    "ansible_base.rbac",
    "ansible_base.resource_registry",
    "ansible_base.jwt_consumer",
    "ansible_base.rest_filters",
    # Local apps
    "aap_eda.api",
    "aap_eda.core",
]

# Defines feature flags, and their conditions.
# See https://cfpb.github.io/django-flags/
FLAGS = {}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "crum.CurrentRequestUserMiddleware",
]

ROOT_URLCONF = "aap_eda.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

WSGI_APPLICATION = "aap_eda.wsgi.application"

ASGI_APPLICATION = "aap_eda.asgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases


def _get_databases_settings() -> dict:
    databases = settings.get("DATABASES", {})
    if databases and "default" not in databases:
        raise ImproperlyConfigured(
            "DATABASES settings must contain a 'default' key"
        )

    if not databases:
        databases["default"] = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": settings.get("DB_HOST", "127.0.0.1"),
            "PORT": settings.get("DB_PORT", 5432),
            "USER": settings.get("DB_USER", "postgres"),
            "PASSWORD": settings.get("DB_PASSWORD"),
            "NAME": settings.get("DB_NAME", "eda"),
            "OPTIONS": {
                "sslmode": settings.get("PGSSLMODE", default="allow"),
                "sslcert": settings.get("PGSSLCERT", default=""),
                "sslkey": settings.get("PGSSLKEY", default=""),
                "sslrootcert": settings.get("PGSSLROOTCERT", default=""),
            },
        }
    return databases


DATABASES = _get_databases_settings()

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",  # noqa: E501
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

USE_I18N = True

TIME_ZONE = "UTC"

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = settings.get("STATIC_URL", "static/")
STATIC_ROOT = settings.get("STATIC_ROOT", "/var/lib/eda/static")

MEDIA_ROOT = settings.get("MEDIA_ROOT", "/var/lib/eda/files")

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "aap_eda.api.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "aap_eda.api.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "aap_eda.api.authentication.WebsocketJWTAuthentication",
        "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "ansible_base.rbac.api.permissions.AnsibleBaseObjectPermissions",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_METADATA_CLASS": "aap_eda.api.metadata.EDAMetadata",
    "EXCEPTION_HANDLER": "aap_eda.api.exceptions.api_fallback_handler",
}


def _config_authentication_backends():
    from django.conf import settings as djsettings

    backend = (
        "ansible_base.lib.backends.prefixed_user_auth.PrefixedUserAuthBackend"
    )
    backends = djsettings.AUTHENTICATION_BACKENDS or []
    if backend not in backends:
        backends.append(backend)
    return backends


RENAMED_USERNAME_PREFIX = settings.get("RENAMED_USERNAME_PREFIX", "eda_")
AUTHENTICATION_BACKENDS = _config_authentication_backends()


# ---------------------------------------------------------
# DEPLOYMENT SETTINGS
# ---------------------------------------------------------

DEPLOYMENT_TYPE = settings.get("DEPLOYMENT_TYPE", "podman")
WEBSOCKET_BASE_URL = settings.get("WEBSOCKET_BASE_URL", "ws://localhost:8000")
WEBSOCKET_SSL_VERIFY = settings.get("WEBSOCKET_SSL_VERIFY", "yes")
WEBSOCKET_TOKEN_BASE_URL = settings.get("WEBSOCKET_TOKEN_BASE_URL", None)
if WEBSOCKET_TOKEN_BASE_URL is None:
    WEBSOCKET_TOKEN_BASE_URL = WEBSOCKET_BASE_URL.replace(
        "ws://", "http://"
    ).replace("wss://", "https://")
PODMAN_SOCKET_URL = settings.get("PODMAN_SOCKET_URL", None)
PODMAN_SOCKET_TIMEOUT = settings.get("PODMAN_SOCKET_TIMEOUT", default=0)
# zero raises an exception, None takes the socket default
if PODMAN_SOCKET_TIMEOUT == 0:
    PODMAN_SOCKET_TIMEOUT = None
PODMAN_MEM_LIMIT = settings.get("PODMAN_MEM_LIMIT", "200m")
PODMAN_ENV_VARS = settings.get("PODMAN_ENV_VARS", {})
PODMAN_MOUNTS = settings.get("PODMAN_MOUNTS", [])
PODMAN_EXTRA_ARGS = settings.get("PODMAN_EXTRA_ARGS", {})
DEFAULT_PULL_POLICY = settings.get("DEFAULT_PULL_POLICY", "Always")
CONTAINER_NAME_PREFIX = settings.get("CONTAINER_NAME_PREFIX", "eda")


# ---------------------------------------------------------
# TASKING SETTINGS
# ---------------------------------------------------------
RQ = {
    "JOB_CLASS": "aap_eda.core.tasking.Job",
    "QUEUE_CLASS": "aap_eda.core.tasking.Queue",
    "SCHEDULER_CLASS": "aap_eda.core.tasking.Scheduler",
    "WORKER_CLASS": "aap_eda.core.tasking.Worker",
}

REDIS_UNIX_SOCKET_PATH = settings.get("MQ_UNIX_SOCKET_PATH", None)
REDIS_HOST = settings.get("MQ_HOST", "localhost")
REDIS_PORT = settings.get("MQ_PORT", 6379)
REDIS_USER = settings.get("MQ_USER", None)
REDIS_USER_PASSWORD = settings.get("MQ_USER_PASSWORD", None)
REDIS_CLIENT_CACERT_PATH = settings.get("MQ_CLIENT_CACERT_PATH", None)
REDIS_CLIENT_CERT_PATH = settings.get("MQ_CLIENT_CERT_PATH", None)
REDIS_CLIENT_KEY_PATH = settings.get("MQ_CLIENT_KEY_PATH", None)
REDIS_TLS = settings.get("MQ_TLS", None)
DEFAULT_REDIS_DB = 0
REDIS_DB = settings.get("MQ_DB", DEFAULT_REDIS_DB)
RQ_REDIS_PREFIX = settings.get("RQ_REDIS_PREFIX", "eda-rq")

# The HA cluster hosts is a string of <host>:<port>[,<host>:port>]+
# and is exhaustive; i.e., not in addition to REDIS_HOST:REDIS_PORT.
# EDA does not validate the content, but relies on DAB to do so.
#
# In establishing an HA Cluster Redis client connection DAB ignores
# the host and port kwargs.
REDIS_HA_CLUSTER_HOSTS = settings.get("MQ_REDIS_HA_CLUSTER_HOSTS", "").strip()


def _rq_common_parameters():
    params = {
        "DB": REDIS_DB,
        "USERNAME": REDIS_USER,
        "PASSWORD": REDIS_USER_PASSWORD,
    }
    if REDIS_UNIX_SOCKET_PATH:
        params["UNIX_SOCKET_PATH"] = REDIS_UNIX_SOCKET_PATH
    else:
        params |= {
            "HOST": REDIS_HOST,
            "PORT": REDIS_PORT,
        }
        if REDIS_TLS:
            params["SSL"] = True
        else:
            # TODO: Deprecate implicit setting based on cert path in favor of
            #       MQ_TLS as the determinant.
            if REDIS_CLIENT_CERT_PATH and REDIS_TLS is None:
                params["SSL"] = True
            else:
                params["SSL"] = False
    return params


def _rq_redis_client_additional_parameters():
    params = {}
    if (not REDIS_UNIX_SOCKET_PATH) and REDIS_CLIENT_CERT_PATH:
        params |= {
            "ssl_certfile": REDIS_CLIENT_CERT_PATH,
            "ssl_keyfile": REDIS_CLIENT_KEY_PATH,
            "ssl_ca_certs": REDIS_CLIENT_CACERT_PATH,
        }
    return params


def rq_standalone_redis_client_instantiation_parameters():
    params = _rq_common_parameters() | _rq_redis_client_additional_parameters()

    # Convert to lowercase for use in instantiating a redis client.
    params = {k.lower(): v for (k, v) in params.items()}
    return params


def rq_redis_client_instantiation_parameters():
    params = rq_standalone_redis_client_instantiation_parameters()

    # Include the HA cluster parameters.
    if REDIS_HA_CLUSTER_HOSTS:
        params["mode"] = "cluster"
        params["redis_hosts"] = REDIS_HA_CLUSTER_HOSTS
        params["socket_keepalive"] = _get_boolean("MQ_SOCKET_KEEP_ALIVE", True)
        params["socket_connect_timeout"] = settings.get(
            "MQ_SOCKET_CONNECT_TIMEOUT", 10
        )
        params["socket_timeout"] = settings.get("MQ_SOCKET_TIMEOUT", 150)
        params["cluster_error_retry_attempts"] = settings.get(
            "MQ_CLUSTER_ERROR_RETRY_ATTEMPTS", 3
        )
        from redis.backoff import ConstantBackoff
        from redis.retry import Retry

        params["retry"] = Retry(backoff=ConstantBackoff(3), retries=20)
    return params


# A list of queues to be used in multinode mode
# If the list is empty, use the default singlenode queue name
RULEBOOK_WORKER_QUEUES = settings.get("RULEBOOK_WORKER_QUEUES", [])
if isinstance(RULEBOOK_WORKER_QUEUES, str):
    RULEBOOK_WORKER_QUEUES = RULEBOOK_WORKER_QUEUES.split(",")

if len(set(RULEBOOK_WORKER_QUEUES)) != len(RULEBOOK_WORKER_QUEUES):
    raise ImproperlyConfigured(
        "The RULEBOOK_WORKER_QUEUES setting must not contain duplicates."
    )

# If the list is empty, use the default queue name for single node mode
if not RULEBOOK_WORKER_QUEUES:
    RULEBOOK_WORKER_QUEUES = ["activation"]

DEFAULT_QUEUE_TIMEOUT = settings.get("DEFAULT_QUEUE_TIMEOUT", 300)
DEFAULT_RULEBOOK_QUEUE_TIMEOUT = settings.get(
    "DEFAULT_RULEBOOK_QUEUE_TIMEOUT", 120
)

# Time window in seconds to consider a worker as dead
DEFAULT_WORKER_HEARTBEAT_TIMEOUT = 60
DEFAULT_WORKER_TTL = 5


def get_rq_queues() -> dict:
    """Construct the RQ_QUEUES dictionary based on the settings."""
    queues = {}

    # Configure the default queue
    queues["default"] = _rq_common_parameters()
    queues["default"]["DEFAULT_TIMEOUT"] = DEFAULT_QUEUE_TIMEOUT
    queues["default"][
        "REDIS_CLIENT_KWARGS"
    ] = _rq_redis_client_additional_parameters()

    # Configure the worker queues
    for queue in RULEBOOK_WORKER_QUEUES:
        queues[queue] = _rq_common_parameters()
        queues[queue]["DEFAULT_TIMEOUT"] = DEFAULT_RULEBOOK_QUEUE_TIMEOUT
        queues[queue][
            "REDIS_CLIENT_KWARGS"
        ] = _rq_redis_client_additional_parameters()

    return queues


RQ_QUEUES = get_rq_queues()

# Queue name for the rulebook workers. To be used in multinode mode
# Otherwise, the default name is used
RULEBOOK_QUEUE_NAME = settings.get("RULEBOOK_QUEUE_NAME", "activation")

RQ_STARTUP_JOBS = []

CELERYBEAT_SCHEDULE = {
    "aap_eda.tasks.orchestrator.monitor_rulebook_processes": {
        "schedule": timedelta(seconds=5)
    },
    "aap_eda.tasks.project._monitor_project_tasks": {
        "schedule": timedelta(seconds=30)
    },
}

RQ_CRON_JOBS = []
RQ_SCHEDULER_JOB_INTERVAL = settings.get("SCHEDULER_JOB_INTERVAL", 5)

# ---------------------------------------------------------
# APPLICATION SETTINGS
# ---------------------------------------------------------

API_PREFIX = settings.get("API_PREFIX", "api/eda").strip("/")

SPECTACULAR_SETTINGS = {
    "TITLE": "Event Driven Ansible API",
    "VERSION": utils.get_eda_version(),
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": f"/{API_PREFIX}/v[0-9]",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "SERVERS": [{"url": f"/{API_PREFIX}/v1"}],
    "PREPROCESSING_HOOKS": [
        "aap_eda.api.openapi.preprocess_filter_api_routes"
    ],
    "GENERIC_ADDITIONAL_PROPERTIES": "bool",
}

# ---------------------------------------------------------
# LOGGING SETTINGS
# ---------------------------------------------------------

APP_LOG_LEVEL = settings.get("APP_LOG_LEVEL", "INFO")

# If DEBUG is set, keep consistent the log level
if DEBUG:
    APP_LOG_LEVEL = "DEBUG"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {name} {levelname:<8} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
        "django.channels.server": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
        "aap_eda": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
        "ansible_base": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
        "dispatcher": {
            "handlers": ["console"],
            "level": "DEBUG",  # TODO: this is for demo!!
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------
# CONTROLLER SETTINGS
# ---------------------------------------------------------

EDA_CONTROLLER_URL = settings.get("CONTROLLER_URL", "default_controller_url")
EDA_CONTROLLER_TOKEN = settings.get(
    "CONTROLLER_TOKEN", "default_controller_token"
)
EDA_CONTROLLER_SSL_VERIFY = settings.get("CONTROLLER_SSL_VERIFY", "yes")

# ---------------------------------------------------------
# RULEBOOK LIVENESS SETTINGS
# ---------------------------------------------------------

RULEBOOK_READINESS_TIMEOUT_SECONDS = int(
    settings.get("RULEBOOK_READINESS_TIMEOUT_SECONDS", 30)
)
RULEBOOK_LIVENESS_CHECK_SECONDS = int(
    settings.get("RULEBOOK_LIVENESS_CHECK_SECONDS", 300)
)
RULEBOOK_LIVENESS_TIMEOUT_SECONDS = (
    int(settings.get("RULEBOOK_LIVENESS_TIMEOUT_SECONDS", 310))
    + RULEBOOK_LIVENESS_CHECK_SECONDS
)
ACTIVATION_RESTART_SECONDS_ON_COMPLETE = int(
    settings.get("ACTIVATION_RESTART_SECONDS_ON_COMPLETE", 0)
)
ACTIVATION_RESTART_SECONDS_ON_FAILURE = int(
    settings.get("ACTIVATION_RESTART_SECONDS_ON_FAILURE", 60)
)
ACTIVATION_MAX_RESTARTS_ON_FAILURE = int(
    settings.get("ACTIVATION_MAX_RESTARTS_ON_FAILURE", 5)
)

# -1 means no limit
MAX_RUNNING_ACTIVATIONS = int(settings.get("MAX_RUNNING_ACTIVATIONS", 5))

# ---------------------------------------------------------
# RULEBOOK ENGINE LOG LEVEL
# ---------------------------------------------------------


# For backwards compatibility, from the old value "-v" to the new value "info"
def get_rulebook_process_log_level() -> RulebookProcessLogLevel:
    log_level = settings.get(
        "ANSIBLE_RULEBOOK_LOG_LEVEL",
        "error",
    )
    if log_level is None:
        return RulebookProcessLogLevel.ERROR
    if log_level.lower() == "-v":
        return RulebookProcessLogLevel.INFO
    if log_level.lower() == "-vv":
        return RulebookProcessLogLevel.DEBUG
    if log_level not in RulebookProcessLogLevel.values():
        raise ImproperlyConfigured(
            f"Invalid log level '{log_level}' for ANSIBLE_RULEBOOK_LOG_LEVEL"
            f" setting. Valid values are: {RulebookProcessLogLevel.values()}"
        )
    return RulebookProcessLogLevel(log_level)


ANSIBLE_RULEBOOK_LOG_LEVEL = get_rulebook_process_log_level()
ANSIBLE_RULEBOOK_FLUSH_AFTER = settings.get(
    "ANSIBLE_RULEBOOK_FLUSH_AFTER", 100
)

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE SETTINGS
# ---------------------------------------------------------
from ansible_base.lib import dynamic_config  # noqa: E402

dab_settings = os.path.join(
    os.path.dirname(dynamic_config.__file__), "dynamic_settings.py"
)
include(dab_settings)

ANSIBLE_BASE_CUSTOM_VIEW_PARENT = "aap_eda.api.views.dab_base.BaseAPIView"

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE JWT SETTINGS
# ---------------------------------------------------------
ANSIBLE_BASE_JWT_VALIDATE_CERT = settings.get(
    "ANSIBLE_BASE_JWT_VALIDATE_CERT", False
)
ANSIBLE_BASE_JWT_KEY = settings.get(
    "ANSIBLE_BASE_JWT_KEY", "https://localhost"
)

# These settings have defaults in DAB
# if the file or env var does not define them, leave as default
if settings.exists("ALLOW_LOCAL_RESOURCE_MANAGEMENT"):
    ALLOW_LOCAL_RESOURCE_MANAGEMENT = settings.get(
        "ALLOW_LOCAL_RESOURCE_MANAGEMENT"
    )

if settings.exists("RESOURCE_SERVICE_PATH"):
    RESOURCE_SERVICE_PATH = settings.get("RESOURCE_SERVICE_PATH")

if settings.exists("RESOURCE_SERVER_SYNC_ENABLED"):
    RESOURCE_SERVER_SYNC_ENABLED = settings.get("RESOURCE_SERVER_SYNC_ENABLED")

if settings.exists("ENABLE_SERVICE_BACKED_SSO"):
    ENABLE_SERVICE_BACKED_SSO = settings.get("ENABLE_SERVICE_BACKED_SSO")

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE RESOURCES REGISTRY SETTINGS
# ---------------------------------------------------------
ANSIBLE_BASE_RESOURCE_CONFIG_MODULE = "aap_eda.api.resource_api"

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE RBAC SETTINGS
# ---------------------------------------------------------
DEFAULT_ORGANIZATION_NAME = "Default"

ANSIBLE_BASE_SERVICE_PREFIX = "eda"

ANSIBLE_BASE_TEAM_MODEL = "core.Team"
ANSIBLE_BASE_ORGANIZATION_MODEL = "core.Organization"

# Organization and object roles will come from create_initial_data
ANSIBLE_BASE_ROLE_PRECREATE = {}

ANSIBLE_BASE_ALLOW_SINGLETON_USER_ROLES = True

ALLOW_LOCAL_ASSIGNING_JWT_ROLES = settings.get(
    "ALLOW_LOCAL_ASSIGNING_JWT_ROLES", False
)

ALLOW_SHARED_RESOURCE_CUSTOM_ROLES = settings.get(
    "ALLOW_SHARED_RESOURCE_CUSTOM_ROLES", False
)

ANSIBLE_BASE_CHECK_RELATED_PERMISSIONS = ["view"]

# --------------------------------------------------------
# DJANGO ANSIBLE BASE RESOURCE API CLIENT
# --------------------------------------------------------
RESOURCE_SERVER = {
    "URL": settings.get("RESOURCE_SERVER__URL", "https://localhost"),
    "SECRET_KEY": settings.get("RESOURCE_SERVER__SECRET_KEY", ""),
    "VALIDATE_HTTPS": settings.get("RESOURCE_SERVER__VALIDATE_HTTPS", False),
}
RESOURCE_JWT_USER_ID = settings.get("RESOURCE_JWT_USER_ID", None)

ANSIBLE_BASE_MANAGED_ROLE_REGISTRY = settings.get(
    "ANSIBLE_BASE_MANAGED_ROLE_REGISTRY", {}
)

if RESOURCE_SERVER["URL"] and RESOURCE_SERVER["SECRET_KEY"]:
    CELERYBEAT_SCHEDULE["aap_eda.tasks.shared_resources.resync_shared_resources"] = {
        "schedule": timedelta(seconds=900)
    }


ACTIVATION_DB_HOST = settings.get(
    "ACTIVATION_DB_HOST", "host.containers.internal"
)

PG_NOTIFY_TEMPLATE_RULEBOOK = settings.get("PG_NOTIFY_TEMPLATE_RULEBOOK", None)

SAFE_PLUGINS_FOR_PORT_FORWARD = settings.get(
    "SAFE_PLUGINS_FOR_PORT_FORWARD",
    ["ansible.eda.webhook", "ansible.eda.alertmanager"],
)

API_PATH_TO_UI_PATH_MAP = settings.get(
    "API_PATH_UI_PATH_MAP", {"/api/controller": "/execution", "/": "/#"}
)

_db_options = DATABASES["default"].get("OPTIONS", {})
_DEFAULT_PG_NOTIFY_DSN_SERVER = (
    f"host={DATABASES['default']['HOST']} "
    f"port={DATABASES['default']['PORT']} "
    f"dbname={DATABASES['default']['NAME']} "
    f"user={DATABASES['default']['USER']} "
    f"password={DATABASES['default']['PASSWORD']} "
    f"sslmode={_db_options.get('sslmode','allow')} "
    f"sslcert={_db_options.get('sslcert','')} "
    f"sslkey={_db_options.get('sslkey','')} "
    f"sslrootcert={_db_options.get('sslrootcert','')} "
)

PG_NOTIFY_DSN_SERVER = settings.get(
    "PG_NOTIFY_DSN_SERVER", _DEFAULT_PG_NOTIFY_DSN_SERVER
)

EVENT_STREAM_BASE_URL = settings.get("EVENT_STREAM_BASE_URL", None)
if EVENT_STREAM_BASE_URL:
    EVENT_STREAM_BASE_URL = EVENT_STREAM_BASE_URL.strip("/") + "/"

EVENT_STREAM_MTLS_BASE_URL = settings.get("EVENT_STREAM_MTLS_BASE_URL", None)
if EVENT_STREAM_MTLS_BASE_URL:
    EVENT_STREAM_MTLS_BASE_URL = EVENT_STREAM_MTLS_BASE_URL.strip("/") + "/"

MAX_PG_NOTIFY_MESSAGE_SIZE = int(
    settings.get("MAX_PG_NOTIFY_MESSAGE_SIZE", 6144)
)

DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME = "_DEFAULT_EDA_PG_NOTIFY_CREDS"
