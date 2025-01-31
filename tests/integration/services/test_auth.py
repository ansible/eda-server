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

import time
from unittest.mock import patch

import pytest

from aap_eda.services.auth import (
    create_jwt_token,
    parse_jwt_token,
    validate_jwt_token,
)
from aap_eda.services.exceptions import InvalidTokenError


@pytest.mark.django_db
def test_create_jwt_token():
    token, refresh = create_jwt_token()

    assert token.count(".") == 2
    assert refresh.count(".") == 2

    validate_jwt_token(token, "access")
    validate_jwt_token(refresh, "refresh")

    assert {"user_id", "exp", "token_type"} <= parse_jwt_token(token).keys()
    assert {"user_id", "exp", "token_type"} <= parse_jwt_token(refresh).keys()


@pytest.mark.django_db
def test_validate_type_exception():
    token, _ = create_jwt_token()
    with pytest.raises(InvalidTokenError) as error_info:
        validate_jwt_token(token, "refresh")
    assert str(error_info.value) == "Invalid token type"


@pytest.mark.django_db
@patch("aap_eda.services.auth.settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES", "0")
def test_token_expired_exception():
    token, _ = create_jwt_token()
    time.sleep(1)
    with pytest.raises(InvalidTokenError) as error_info:
        parse_jwt_token(token)
    assert str(error_info.value) == "Expired token"
