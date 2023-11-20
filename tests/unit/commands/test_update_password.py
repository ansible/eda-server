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
from io import StringIO

import pytest
from django.core.management import base, call_command

from aap_eda.core import models


@pytest.mark.django_db
def test_update_password_successful():
    username = "testadmin"
    user_email = "admin@test.com"
    user = models.User.objects.create(
        username=username, password="pass", email=user_email
    )
    new_password = "password"
    out = StringIO()
    kwargs = {
        "stdout": out,
        "username": user.username,
        "password": new_password,
    }

    call_command("update_password", **kwargs)

    user.refresh_from_db()
    assert (
        out.getvalue()
        == f"Successfully updated the password of user '{username}'\n"
    )
    assert user.username == username
    assert user.email == user_email
    assert user.check_password(new_password)


@pytest.mark.django_db
def test_update_password_missing_args():
    kwargs = {"username": "testadmin"}
    try:
        call_command("update_password", **kwargs)
    except base.CommandError as e:
        assert (
            str(e)
            == "Error: the following arguments are required: -p/--password"
        )

    kwargs = {"password": "password"}
    try:
        call_command("update_password", **kwargs)
    except base.CommandError as e:
        assert (
            str(e)
            == "Error: the following arguments are required: -u/--username"
        )


@pytest.mark.django_db
def test_update_password_user_not_found():
    username = "non-existent-user"
    kwargs = {"username": username, "password": "password"}
    try:
        call_command("update_password", **kwargs)
    except base.CommandError as e:
        assert str(e) == f"User '{username}' does not exist."
