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
from typing import Optional, Tuple

import requests
import yaml
from django.utils.dateparse import parse_datetime
from requests.auth import AuthBase, HTTPBasicAuth

from aap_eda.core import enums, models

logger = logging.getLogger("aap_eda.analytics")


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
