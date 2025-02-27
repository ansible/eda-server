#  Copyright 2024 Red Hat, Inc.
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
import re
from functools import lru_cache
from typing import Any, Optional, Tuple

import requests
import yaml
from django.conf import settings
from django.utils.dateparse import parse_datetime
from requests.auth import AuthBase, HTTPBasicAuth

from aap_eda.conf import application_settings
from aap_eda.core import enums, models
from aap_eda.core.utils.credentials import inputs_from_store

logger = logging.getLogger("aap_eda.analytics")


class MissingUserPasswordError(Exception):
    """Raised when required user credentials are missing."""

    pass


CREDENTIAL_SOURCES = [
    ("REDHAT", ("REDHAT_USERNAME", "REDHAT_PASSWORD")),
    ("SUBSCRIPTIONS", ("SUBSCRIPTIONS_USERNAME", "SUBSCRIPTIONS_PASSWORD")),
]


class TokenAuth(AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


def datetime_hook(dt: dict) -> dict:
    new_dt = {}
    for key, value in dt.items():
        try:
            new_dt[key] = parse_datetime(value) or value
        except (TypeError, ValueError):
            new_dt[key] = value
    return new_dt


def collect_controllers_info() -> dict:
    aap_credential_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )
    credentials = models.EdaCredential.objects.filter(
        credential_type=aap_credential_type
    )
    info = {}

    for credential in credentials:
        try:
            inputs = yaml.safe_load(credential.inputs.get_secret_value())
            host = inputs["host"].removesuffix("/api/controller/")
            if not info.get(host):
                url = f"{host}/api/v2/ping/"
                auth = _get_auth(inputs)
                verify = inputs.get("verify_ssl", False)

                controller_info = {
                    "credential_id": credential.id,
                    "inputs": inputs,
                }

                # quickly to retrieve controller's info. timeout=3
                resp = requests.get(url, auth=auth, verify=verify, timeout=3)
                resp.raise_for_status()
                controller_info["install_uuid"] = resp.json()["install_uuid"]
                info[host] = controller_info

        except KeyError as e:
            logger.error(f"Missing key in credential inputs: {e}")
            continue
        except yaml.YAMLError as e:
            logger.error(
                f"YAML parsing error for credential {credential.id}: {e}"
            )
            continue
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Controller connection failed for {credential.name}: {e}"
            )
            continue
        except Exception as e:
            logger.exception(
                f"Unexpected error processing credential {credential.id}: {e}"
            )
            continue

    return info


def _get_auth(inputs: dict) -> AuthBase:
    # priority：Token > Basic Auth
    if token := inputs.get("oauth_token"):
        logger.debug("Use Bearer authentication")
        return TokenAuth(token)

    username = inputs.get("username")
    password = inputs.get("password")
    if username and password:
        logger.debug("Use Basic authentication")
        return HTTPBasicAuth(username, password)

    raise ValueError(
        "Invalid authentication configuration, must provide "
        "Token or username/password"
    )


def extract_job_details(
    url: str,
    controllers_info: dict,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    for host, info in controllers_info.items():
        if not url.lower().startswith(host.lower()):
            continue

        install_uuid = info.get("install_uuid")
        if not install_uuid:
            continue

        pattern = r"/jobs/([a-zA-Z]+)/(\d+)/"

        match = re.search(pattern, url)

        if match:
            job_type = match.group(1)
            job_type = (
                "run_job_template"
                if job_type == "playbook"
                else "run_workflow_template"
            )
            job_number = match.group(2)
            return job_type, str(job_number), install_uuid

    return None, None, None


def _get_credential_value(field: str, *setting_envs: Tuple[Any, str]) -> str:
    credential = _get_analytics_credential()
    if credential:
        inputs = inputs_from_store(credential.inputs.get_secret_value())
        return inputs.get(field)

    for env, key in setting_envs:
        if value := getattr(env, key, None):
            return value
    raise ValueError(f"No valid {field} found")


def get_analytics_url() -> str:
    return _get_credential_value(
        "analytics_url",
        (application_settings, "AUTOMATION_ANALYTICS_URL"),
        (settings, "AUTOMATION_ANALYTICS_URL"),
    )


def get_username() -> str:
    validate_credential()
    return _get_credential_value(
        "username",
        (settings, "REDHAT_USERNAME"),
        (application_settings, "REDHAT_USERNAME"),
        (application_settings, "SUBSCRIPTIONS_USERNAME"),
    )


def get_password() -> str:
    validate_credential()
    return _get_credential_value(
        "password",
        (settings, "REDHAT_PASSWORD"),
        (application_settings, "REDHAT_PASSWORD"),
        (application_settings, "SUBSCRIPTIONS_PASSWORD"),
    )


def get_analytics_interval() -> str:
    return _get_credential_value(
        "gather_interval",
        (application_settings, "AUTOMATION_ANALYTICS_GATHER_INTERVAL"),
    )


def validate_credential() -> None:
    if _get_analytics_credential():
        return

    has_valid = []
    for setting in (application_settings, settings):
        for _, keys in CREDENTIAL_SOURCES:
            has_valid.append(
                getattr(setting, keys[0], None)
                and getattr(setting, keys[1], None)
            )

    if not any(has_valid):
        logger.error("Missing required credentials in settings")
        raise MissingUserPasswordError("Valid credentials not found")


@lru_cache(maxsize=1)
def _get_analytics_credential():
    analytics_type = models.CredentialType.objects.get(
        name=enums.AnalyticsCredentialType.BASIC
    )
    return models.EdaCredential.objects.filter(
        credential_type=analytics_type
    ).first()
