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
import json
import os
from io import StringIO

import pytest
from django.core.management import call_command

try:
    from ansible_base.authentication.models import Authenticator
except ImportError:
    raise ImportError(
        "The 'ansible_base' module or its models could not be imported."
    )


@pytest.mark.django_db
def test_dump_auth_config_successful(tmpdir):
    auth_data = {
        "name": "Dev LDAP Container",
        "enabled": True,
        "configuration": {
            "BIND_DN": "cn=admin,dc=example,dc=org",
            "BIND_PASSWORD": "admin",
            "CONNECTION_OPTIONS": {
                "OPT_REFERRALS": 0,
                "OPT_NETWORK_TIMEOUT": 30,
            },
        },
        "type": "aap_eda.core.authenticator_plugins.ldap",
    }
    Authenticator.objects.create(**auth_data)
    out = StringIO()
    output_file = os.path.join(tmpdir, "test_dump.json")
    call_command("dump_auth_config", output_file, stdout=out)

    assert os.path.exists(output_file)

    with open(output_file) as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert data[0]["type"] == auth_data["type"]
        assert data[0]["configuration"] == auth_data["configuration"]

    os.remove(output_file)


@pytest.mark.django_db
def test_dump_auth_config_empty_data(tmpdir):
    out = StringIO()
    output_file = os.path.join(tmpdir, "test_dump.json")
    call_command("dump_auth_config", output_file, stdout=out)

    assert os.path.exists(output_file)

    with open(output_file) as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert data == []

    os.remove(output_file)
