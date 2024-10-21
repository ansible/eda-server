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
"""Common Attributes for Engine Tests."""

import pytest
from dateutil import parser

from aap_eda.core import models

from .utils import InitData


def _common_data(
    default_organization: models.Organization,
    k8s_service_name: str = None,
) -> InitData:
    user = models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )
    activation = models.Activation.objects.create(
        name="activation",
        k8s_service_name=k8s_service_name,
        user=user,
        organization=default_organization,
    )
    activation_instance = models.RulebookProcess.objects.create(
        name="test-instance",
        log_read_at=parser.parse("2023-10-30T19:18:48.362883381Z"),
        activation=activation,
        organization=default_organization,
    )

    return InitData(
        activation=activation,
        activation_instance=activation_instance,
    )


@pytest.fixture()
def init_kubernetes_data(
    default_organization: models.Organization,
) -> InitData:
    return _common_data(default_organization, "test_k8s_service")


@pytest.fixture()
def init_podman_data(
    default_organization: models.Organization,
) -> InitData:
    return _common_data(default_organization)
