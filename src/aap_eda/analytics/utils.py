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

import base64
import logging
import re
from typing import Optional, Tuple

import requests
import yaml
from django.utils.dateparse import parse_datetime

from aap_eda.core import enums, models
from aap_eda.utils import str_to_bool

logger = logging.getLogger("aap_eda.analytics")


def datetime_hook(dt: dict) -> dict:
    new_dt = {}
    for key, value in dt.items():
        try:
            new_dt[key] = parse_datetime(value)
        except TypeError:
            new_dt[key] = value
    return new_dt


def collect_controllers_info() -> dict:
    aap_credentia_type = models.CredentialType.objects.get(
        name=enums.DefaultCredentialType.AAP
    )
    credentials = models.EdaCredential.objects.filter(
        credential_type=aap_credentia_type
    )
    info = {}
    for credential in credentials:
        controller_info = {}
        inputs = yaml.safe_load(credential.inputs.get_secret_value())
        host = inputs["host"]
        url = f"{host}/api/v2/ping/"
        verify = str_to_bool(inputs.get("verify_ssl", ""))
        token = inputs.get("oauth_token")

        controller_info["credential_id"] = credential.id
        controller_info["inputs"] = inputs
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            logger.info("Use Bearer token to ping the controller.")
        else:
            user_pass = f"{inputs.get('username')}:{inputs.get('password')}"
            auth_value = (
                f"Basic {base64.b64encode(user_pass.encode()).decode()}"
            )
            headers = {"Authorization": f"{auth_value}"}
            logger.info("Use Basic authentication to ping the controller.")

        try:
            resp = requests.get(url, headers=headers, verify=verify)
            resp_json = resp.json()
            controller_info["install_uuid"] = resp_json["install_uuid"]

            info[host] = controller_info
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Failed to connect with controller using credential "
                f"{credential.name}: {e}"
            )

    return info


def extract_job_details(
    url: str,
    controllers_info: dict,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    for host, info in controllers_info.items():
        if not url.startswith(host):
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
            return job_type, str(job_number), info["install_uuid"]

    return None, None, None
