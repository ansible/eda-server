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
from typing import Optional, get_type_hints

from django.core.exceptions import ImproperlyConfigured
from dynaconf import Dynaconf

from aap_eda import utils
from aap_eda.core.enums import RulebookProcessLogLevel

from . import defaults


def _get_secret_key(settings: Dynaconf) -> str:
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


def get_boolean(settings: Dynaconf, name: str, default=False) -> bool:
    value = settings.get(name, default)
    if isinstance(value, str):
        value = utils.str_to_bool(value)
    if not isinstance(value, bool):
        raise ImproperlyConfigured("{name} setting must be a boolean value.")
    return value


def _get_list_from_str(settings: Dynaconf, name: str) -> list:
    value = settings.get(name, [])
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        raise ImproperlyConfigured(
            f"{name} setting must be a list or comma separated string."
        )
    return value


def _get_stripped_str(settings: Dynaconf, name: str) -> str:
    value = settings.get(name)
    if value:
        return value.strip()
    return value


def _get_int(settings: Dynaconf, name: str) -> int:
    try:
        return int(settings.get(name))
    except (ValueError, TypeError):
        raise ImproperlyConfigured(f"{name} setting must be an interger.")


def _get_url_end_slash(settings: Dynaconf, name: str) -> str:
    value = settings.get(name)
    if not isinstance(value, Optional[str]):
        raise ImproperlyConfigured(f"{name} setting must be a string.")
    if value:
        return value.rstrip("/") + "/"
    return value


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases


def _get_databases_settings(settings: Dynaconf) -> dict:
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


def _config_authentication_backends():
    from django.conf import settings as djsettings

    backend = (
        "ansible_base.lib.backends.prefixed_user_auth.PrefixedUserAuthBackend"
    )
    backends = djsettings.AUTHENTICATION_BACKENDS or []
    if backend not in backends:
        backends.append(backend)
    return backends


def _rq_common_parameters(settings: Dynaconf):
    params = {
        "DB": settings.REDIS_DB,
        "USERNAME": settings.REDIS_USER,
        "PASSWORD": settings.REDIS_USER_PASSWORD,
    }
    if settings.REDIS_UNIX_SOCKET_PATH:
        params["UNIX_SOCKET_PATH"] = settings.REDIS_UNIX_SOCKET_PATH
    else:
        params |= {
            "HOST": settings.REDIS_HOST,
            "PORT": settings.REDIS_PORT,
        }
        if settings.REDIS_TLS:
            params["SSL"] = True
        else:
            # TODO: Deprecate implicit setting based on cert path in favor of
            #       MQ_TLS as the determinant.
            if settings.REDIS_CLIENT_CERT_PATH and settings.REDIS_TLS is None:
                params["SSL"] = True
            else:
                params["SSL"] = False
    return params


def _rq_redis_client_additional_parameters(settings: Dynaconf):
    params = {}
    if (
        not settings.REDIS_UNIX_SOCKET_PATH
    ) and settings.REDIS_CLIENT_CERT_PATH:
        params |= {
            "ssl_certfile": settings.REDIS_CLIENT_CERT_PATH,
            "ssl_keyfile": settings.REDIS_CLIENT_KEY_PATH,
            "ssl_ca_certs": settings.REDIS_CLIENT_CACERT_PATH,
        }
    return params


def get_rq_queues(settings: Dynaconf) -> dict:
    """Construct the RQ_QUEUES dictionary based on the settings."""
    queues = {}

    # Configure the default queue
    queues["default"] = _rq_common_parameters(settings)
    queues["default"]["DEFAULT_TIMEOUT"] = settings.DEFAULT_QUEUE_TIMEOUT
    queues["default"][
        "REDIS_CLIENT_KWARGS"
    ] = _rq_redis_client_additional_parameters(settings)

    # Configure the worker queues
    for queue in settings.RULEBOOK_WORKER_QUEUES:
        queues[queue] = _rq_common_parameters(settings)
        queues[queue][
            "DEFAULT_TIMEOUT"
        ] = settings.DEFAULT_RULEBOOK_QUEUE_TIMEOUT
        queues[queue][
            "REDIS_CLIENT_KWARGS"
        ] = _rq_redis_client_additional_parameters(settings)

    return queues


# For backwards compatibility, from the old value "-v" to the new value "info"
def get_rulebook_process_log_level(
    settings: Dynaconf,
) -> RulebookProcessLogLevel:
    log_level = settings.ANSIBLE_RULEBOOK_LOG_LEVEL
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


def _get_spectacular_settings(settings: Dynaconf) -> dict:
    return {
        "TITLE": "Event Driven Ansible API",
        "VERSION": utils.get_package_version("aap-eda"),
        "SERVE_INCLUDE_SCHEMA": False,
        "SCHEMA_PATH_PREFIX": f"/{settings.API_PREFIX}/v[0-9]",
        "SCHEMA_PATH_PREFIX_TRIM": True,
        "SERVERS": [{"url": f"/{settings.API_PREFIX}/v1"}],
        "PREPROCESSING_HOOKS": [
            "aap_eda.api.openapi.preprocess_filter_api_routes"
        ],
        "GENERIC_ADDITIONAL_PROPERTIES": "bool",
    }


def _get_logging_setup(settings: Dynaconf) -> dict:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "{asctime} {name} {levelname:<8} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
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
                "level": settings.APP_LOG_LEVEL,
                "propagate": False,
            },
            "django.channels.server": {
                "handlers": ["console"],
                "level": settings.APP_LOG_LEVEL,
                "propagate": False,
            },
            "aap_eda": {
                "handlers": ["console"],
                "level": settings.APP_LOG_LEVEL,
                "propagate": False,
            },
            "ansible_base": {
                "handlers": ["console"],
                "level": settings.APP_LOG_LEVEL,
                "propagate": False,
            },
        },
    }


def _get_default_pg_notify_dsn_server(settings: Dynaconf) -> str:
    db_options = settings.DATABASES["default"].get("OPTIONS", {})
    return (
        f"host={settings.DATABASES['default']['HOST']} "
        f"port={settings.DATABASES['default']['PORT']} "
        f"dbname={settings.DATABASES['default']['NAME']} "
        f"user={settings.DATABASES['default']['USER']} "
        f"password={settings.DATABASES['default']['PASSWORD']} "
        f"sslmode={db_options.get('sslmode','allow')} "
        f"sslcert={db_options.get('sslcert','')} "
        f"sslkey={db_options.get('sslkey','')} "
        f"sslrootcert={db_options.get('sslrootcert','')} "
    )


def _set_resource_server(settings: Dynaconf) -> None:
    if (
        settings.RESOURCE_SERVER["URL"]
        and settings.RESOURCE_SERVER["SECRET_KEY"]
    ):
        jobs = settings.RQ_PERIODIC_JOBS
        jobs.append(
            {
                "func": "aap_eda.tasks.shared_resources.resync_shared_resources",  # noqa: E501
                "interval": 900,
                "id": "resync_shared_resources",
            }
        )
        settings.RQ_PERIODIC_JOBS = jobs


def _enforce_types(settings: Dynaconf) -> None:
    for key, key_type in get_type_hints(defaults).items():
        if key_type == defaults.StrToList:
            settings[key] = _get_list_from_str(settings, key)
        elif key_type == bool:
            settings[key] = get_boolean(settings, key)
        elif key_type == int:
            settings[key] = _get_int(settings, key)
        elif key_type == defaults.UrlSlash:
            settings[key] = _get_url_end_slash(settings, key)
        elif not isinstance(settings[key], key_type):
            raise ImproperlyConfigured(
                f"{key} setting must be a {key_type.__name__}"
            )
        elif key_type == str or key_type == Optional[str]:
            settings[key] = _get_stripped_str(settings, key)


def post_loading(loaded_settings: Dynaconf):
    # working on a copy first
    settings = Dynaconf()
    settings.update(loaded_settings.to_dict())

    _enforce_types(settings)

    settings.SECRET_KEY = _get_secret_key(settings)
    settings.DATABASES = _get_databases_settings(settings)
    settings.AUTHENTICATION_BACKENDS = _config_authentication_backends()

    if settings.get("WEBSOCKET_TOKEN_BASE_URL", None) is None:
        settings.WEBSOCKET_TOKEN_BASE_URL = (
            settings.WEBSOCKET_BASE_URL.replace("ws://", "http://").replace(
                "wss://", "https://"
            )
        )
    # zero raises an exception, None takes the socket default
    if settings.get("PODMAN_SOCKET_TIMEOUT", 0) == 0:
        settings.PODMAN_SOCKET_TIMEOUT = None

    settings.REDIS_UNIX_SOCKET_PATH = settings.get("MQ_UNIX_SOCKET_PATH", None)
    settings.REDIS_HOST = settings.get("MQ_HOST", "localhost")
    settings.REDIS_PORT = settings.get("MQ_PORT", 6379)
    settings.REDIS_USER = settings.get("MQ_USER", None)
    settings.REDIS_USER_PASSWORD = settings.get("MQ_USER_PASSWORD", None)
    settings.REDIS_CLIENT_CACERT_PATH = settings.get(
        "MQ_CLIENT_CACERT_PATH", None
    )
    settings.REDIS_CLIENT_CERT_PATH = settings.get("MQ_CLIENT_CERT_PATH", None)
    settings.REDIS_CLIENT_KEY_PATH = settings.get("MQ_CLIENT_KEY_PATH", None)
    settings.REDIS_TLS = settings.get("MQ_TLS", None)
    settings.REDIS_DB = settings.get("MQ_DB", settings.DEFAULT_REDIS_DB)
    settings.REDIS_HA_CLUSTER_HOSTS = settings.get(
        "MQ_REDIS_HA_CLUSTER_HOSTS", ""
    )

    if len(set(settings.RULEBOOK_WORKER_QUEUES)) != len(
        settings.RULEBOOK_WORKER_QUEUES
    ):
        raise ImproperlyConfigured(
            "The RULEBOOK_WORKER_QUEUES setting must not contain duplicates."
        )

    # If the list is empty, use the default queue name for single node mode
    if not settings.RULEBOOK_WORKER_QUEUES:
        settings.RULEBOOK_WORKER_QUEUES = ["activation"]

    settings.RQ_SCHEDULER_JOB_INTERVAL = settings.SCHEDULER_JOB_INTERVAL
    settings.RQ_QUEUES = get_rq_queues(settings)

    # ---------------------------------------------------------
    # APPLICATION SETTINGS
    # ---------------------------------------------------------
    settings.API_PREFIX = settings.API_PREFIX.strip("/")
    settings.SPECTACULAR_SETTINGS = _get_spectacular_settings(settings)

    # ---------------------------------------------------------
    # LOGGING SETTINGS
    # ---------------------------------------------------------
    # If DEBUG is set, keep consistent the log level
    if settings.DEBUG:
        settings.APP_LOG_LEVEL = "DEBUG"
    settings.LOGGING = _get_logging_setup(settings)

    settings.EDA_CONTROLLER_URL = settings.CONTROLLER_URL
    settings.EDA_CONTROLLER_TOKEN = settings.CONTROLLER_TOKEN
    settings.EDA_CONTROLLER_SSL_VERIFY = settings.CONTROLLER_SSL_VERIFY

    settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS = (
        settings.RULEBOOK_LIVENESS_TIMEOUT_SECONDS
        + settings.RULEBOOK_LIVENESS_CHECK_SECONDS
    )

    settings.ANSIBLE_RULEBOOK_LOG_LEVEL = get_rulebook_process_log_level(
        settings
    )

    _set_resource_server(settings)

    if not settings.PG_NOTIFY_DSN_SERVER:
        settings.PG_NOTIFY_DSN_SERVER = _get_default_pg_notify_dsn_server(
            settings
        )

    settings.API_PATH_TO_UI_PATH_MAP = settings.API_PATH_UI_PATH_MAP

    data = {
        key: settings[key]
        for key in settings
        if key not in loaded_settings or settings[key] != loaded_settings[key]
    }
    loaded_settings.update(data, loader_identifier="settings:post_loading")
