#  Copyright 2023 Red Hat, Inc.
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
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@pytest.mark.django_db
def test_get_next_link(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/projects/?page_size=1")
    assert (
        response.data["next"] == f"{api_url_v1}/projects/?page=2&page_size=1"
    )

    response = admin_client.get(f"{api_url_v1}/projects/?page=2&page_size=1")
    assert response.data["next"] is None


@pytest.mark.django_db
def test_get_previous_link(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/projects/?page=2&page_size=1")
    assert (
        response.data["previous"]
        == f"{api_url_v1}/projects/?page=1&page_size=1"
    )

    response = admin_client.get(f"{api_url_v1}/projects/?page=1&page_size=1")
    assert response.data["previous"] is None


@pytest.mark.django_db
def test_return_page(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/projects/?page=2&page_size=1")
    assert response.data["page"] == 2


@pytest.mark.django_db
def test_return_page_size(
    default_project: models.Project,
    new_project: models.Project,
    admin_client: APIClient,
):
    response = admin_client.get(f"{api_url_v1}/projects/?page=2&page_size=1")
    assert response.data["page_size"] == 1
