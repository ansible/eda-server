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
from aap_eda.services.ruleset.activation_db_logger import ActivationDbLogger


@pytest.fixture()
def init_data():
    user = models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )
    activation = models.Activation.objects.create(
        name="activation",
        user=user,
    )
    activation_instance = models.ActivationInstance.objects.create(
        name="test-instance",
        activation=activation,
    )

    return activation_instance


@pytest.fixture
def use_dummy_flush_at_end(settings):
    settings.ANSIBLE_RULEBOOK_FLUSH_AFTER = "end"


@pytest.fixture
def use_dummy_flush_after_2(settings):
    settings.ANSIBLE_RULEBOOK_FLUSH_AFTER = "2"


@pytest.mark.django_db
def test_activation_db_logger_end(init_data, use_dummy_flush_at_end):
    activation_instance = init_data
    activation_db_logger = ActivationDbLogger(activation_instance.id)
    activation_db_logger.write("Hello")
    activation_db_logger.write(["Hello", "World"])
    activation_db_logger.flush()

    assert models.ActivationInstanceLog.objects.count() == 3
    assert activation_db_logger.lines_written() == 3


@pytest.mark.django_db
def test_activation_db_logger_intermittent(init_data, use_dummy_flush_after_2):
    activation_instance = init_data
    activation_db_logger = ActivationDbLogger(activation_instance.id)
    activation_db_logger.write("Hello")
    activation_db_logger.write("World")
    activation_db_logger.write(["Fred", "Barney"])
    activation_db_logger.flush()

    assert models.ActivationInstanceLog.objects.count() == 4
    assert activation_db_logger.lines_written() == 4
