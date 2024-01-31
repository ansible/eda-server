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


@pytest.fixture()
def new_user():
    return models.User.objects.create(
        username="tester",
        password="secret",
        first_name="Adam",
        last_name="Tester",
        email="adam@example.com",
    )


@pytest.fixture()
def new_activation(new_user):
    return models.Activation.objects.create(
        name="activation",
        user=new_user,
    )


@pytest.fixture()
def new_event_stream(new_user):
    return models.EventStream.objects.create(
        name="event_stream",
        user=new_user,
    )
