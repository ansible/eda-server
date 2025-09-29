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
import re

from aap_eda.api.vault import (
    AnsibleVaultDecryptionFailed,
    AnsibleVaultEncryptionFailed,
    decrypt,
    encrypt_string,
)

PASSWORD = "secret"
CORE = r"Decryption failed \(no vault secrets were found that could decrypt\)"
RE_ERROR_MSG = re.compile(CORE, re.IGNORECASE | re.DOTALL)
label = "EDA"


@pytest.mark.parametrize(
    "plaintext", ["abc", "space between", "preserve   spaces"]
)
def test_vault_strings(plaintext):
    vault_string = encrypt_string(PASSWORD, plaintext, label)
    decrypted_value = decrypt(PASSWORD, vault_string)

    assert label in vault_string
    assert plaintext == decrypted_value


def test_encrypt_with_exception():
    with pytest.raises(AnsibleVaultEncryptionFailed):
        encrypt_string("bad", None, label)


def test_failed_decrypt():
    vault_string = encrypt_string(PASSWORD, "abc", label)

    with pytest.raises(AnsibleVaultDecryptionFailed, match=RE_ERROR_MSG):
        decrypt("bad", vault_string)
