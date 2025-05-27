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
import logging
import platform
import sys

from django.conf import settings

from aap_eda.utils import get_package_version


class UnconditionalLogger:
    """Log unconditional messages regardless of log level."""

    unconditional_level = sys.maxsize
    unconditional_level_name = "ALWAYS"

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        logging.addLevelName(
            self.unconditional_level,
            self.unconditional_level_name,
        )

    def log(self, *args, **kwargs):
        """Log at the unconditional level."""
        self.logger.log(self.unconditional_level, *args, **kwargs)


# Whitelist of settings that are safe to log at startup
# There are many, only the most relevant, configurable ones are listed here
SETTINGS_LIST_FOR_LOGGING = [
    "DEBUG",
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "JWT_ACCESS_TOKEN_LIFETIME_MINUTES",
    "JWT_REFRESH_TOKEN_LIFETIME_DAYS",
    "FLAGS",
    "DEPLOYMENT_TYPE",
    "WEBSOCKET_BASE_URL",
    "WEBSOCKET_TOKEN_BASE_URL",
    "PODMAN_SOCKET_URL",
    "PODMAN_ENV_VARS",
    "PODMAN_ENV_VARS",
    "PODMAN_MOUNTS",
    "PODMAN_EXTRA_ARGS",
    "REDIS_HOST",
    "RULEBOOK_WORKER_QUEUES",
    "RULEBOOK_QUEUE_NAME",
    "APP_LOG_LEVEL",
    "RULEBOOK_READINESS_TIMEOUT_SECONDS",
    "RULEBOOK_LIVENESS_CHECK_SECONDS",
    "RULEBOOK_LIVENESS_TIMEOUT_SECONDS",
    "ACTIVATION_RESTART_SECONDS_ON_COMPLETE",
    "ACTIVATION_RESTART_SECONDS_ON_FAILURE",
    "ACTIVATION_MAX_RESTARTS_ON_FAILURE",
    "MAX_RUNNING_ACTIVATIONS",
    "ANSIBLE_RULEBOOK_LOG_LEVEL",
    "ALLOW_LOCAL_RESOURCE_MANAGEMENT",
    "RESOURCE_JWT_USER_ID",
    "ANSIBLE_BASE_MANAGED_ROLE_REGISTRY",
    "ACTIVATION_DB_HOST",
    "SAFE_PLUGINS_FOR_PORT_FORWARD",
    "EVENT_STREAM_BASE_URL",
]

LOGGING_PACKAGE_VERSIONS = [
    "podman",
    "kubernetes",
    "django-ansible-base",
]


def startup_logging(logger: logging.Logger) -> None:
    """Log unconditional messages for startup."""
    unconditional_logger = UnconditionalLogger(logger)

    unconditional_logger.log(
        f"Starting eda-server {get_package_version('aap-eda')}",
    )
    unconditional_logger.log(f"Python version: {platform.python_version()}")
    for pkg in LOGGING_PACKAGE_VERSIONS:
        unconditional_logger.log(
            f"{pkg} library version: {get_package_version(pkg)}",
        )
    unconditional_logger.log(
        f"Platform: {platform.platform()} {platform.architecture()}",
    )
    unconditional_logger.log("Static settings:")

    # Database settings
    unconditional_logger.log("  Default database:")
    if not settings.DATABASES or not settings.DATABASES.get("default"):
        logger.error(
            "Expected setting DATABASES not found or empty",
        )
    for setting in ["USER", "HOST", "PORT", "OPTIONS"]:
        value = settings.DATABASES["default"].get(setting)
        unconditional_logger.log(f"    {setting}: {value}")
    # Resource server is relevant but can contain sensitive information
    resource_server = settings.RESOURCE_SERVER.get("URL")
    unconditional_logger.log(f"  Resource server: {resource_server}")

    for setting in SETTINGS_LIST_FOR_LOGGING:
        if hasattr(settings, setting):
            unconditional_logger.log(
                f"  {setting}: {getattr(settings, setting)}",
            )
        else:
            logger.error(f"Expected setting {setting} not found")
