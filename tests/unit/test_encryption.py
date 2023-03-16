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

from aap_eda.core.utils.crypto.fields import decrypt_string, encrypt_string


@pytest.fixture(autouse=True)
def use_dummy_secret_key(settings):
    settings.SECRET_KEY = "secret"


def test_encrypt_decrypt_string():
    value = "A test value!"

    encrypted = encrypt_string(value)
    assert encrypted.startswith("$encrypted$fernet-256$")

    decrypted = decrypt_string(encrypted)
    assert decrypted == value


def test_decrypt_invalid_string():
    with pytest.raises(ValueError):
        decrypt_string("Invalid string")
