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
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["enable", "restart", "disable"])
def test_activation_actions(
    cls_factory, user, user_api_client, give_obj_perm, action
):
    activation = cls_factory.create(models.Activation)
    url = reverse(f"activation-{action}", kwargs={"pk": activation.pk})

    # assure GET is not enabled, so we do not have to permission check it
    response = user_api_client.get(url)
    assert response.status_code == 405, response.data

    # no action permission, denied
    give_obj_perm(user, activation, "view")
    response = user_api_client.post(url)
    assert response.status_code == 403, response.data

    # no permission, denied
    give_obj_perm(user, activation, action)
    response = user_api_client.post(url)
    assert response.status_code == 204, response.data
