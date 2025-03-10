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
import pytest
from django.conf import settings

from aap_eda.utils import get_package_version
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_v1_config(admin_client):
    response = admin_client.get(f"{api_url_v1}/config/")
    assert response.status_code == 200
    assert response.data == {
        "time_zone": settings.TIME_ZONE,
        "version": get_package_version("aap-eda"),
        "deployment_type": settings.DEPLOYMENT_TYPE,
    }
