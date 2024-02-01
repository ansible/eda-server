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

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus


@pytest.mark.django_db
def test_activation_latest_instance_field(new_activation):
    """Test latest_instance field is updated when a new instance is created."""
    activation = new_activation
    assert activation.latest_instance is None

    first_instance = models.RulebookProcess.objects.create(
        activation=activation,
        name="instance",
        status=ActivationStatus.PENDING,
    )
    assert activation.latest_instance == first_instance

    second_instance = models.RulebookProcess.objects.create(
        activation=activation,
        name="instance",
        status=ActivationStatus.PENDING,
    )
    assert activation.latest_instance == second_instance

    # ensure latest instance is returned when a previous instance is updated
    first_instance.status = ActivationStatus.COMPLETED
    first_instance.save(update_fields=["status"])
    assert activation.latest_instance == second_instance
