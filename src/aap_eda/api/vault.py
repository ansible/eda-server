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
import os
import shutil
import tempfile

import pexpect


class AnsibleVaultNotFound(Exception):
    pass


class AnsibleVaultEncryptionFailed(Exception):
    pass


class AnsibleVaultDecryptionFailed(Exception):
    pass


VAULT_COMMAND = shutil.which("ansible-vault")
if VAULT_COMMAND is None:
    raise AnsibleVaultNotFound("Cannot find ansible-vault executable")


def encrypt_string(password: str, plaintext: str, vault_id: str) -> str:
    try:
        tmp = tempfile.NamedTemporaryFile("w+t")
        os.chmod(tmp.name, 0o600)
        tmp.write(password)
        tmp.flush()
        label = f"{vault_id}@{tmp.name}"

        child = pexpect.spawn(
            f"ansible-vault encrypt_string --vault-id {label}"
        )
        child.expect("Reading plaintext input from stdin*")
        child.sendline(plaintext)
        child.sendcontrol("D")
    except Exception as e:
        msg = "Failed to encrypt string"
        raise AnsibleVaultEncryptionFailed(msg) from e

    encrypted_successful_found = False
    encrypted_start = False
    encrypted_str = ""

    # Different versions of ansible-core output the "Encryption Successful"
    # either at the beginning or at the end, right after the data.
    # This logic accounts for all the variants we have seen so far in the
    # output of ansible-vault.

    for line in child.readlines():
        out = line.decode().lstrip()
        if out.startswith("!vault"):
            encrypted_start = True
            continue

        if "Encryption successful" in out:
            encrypted_successful_found = True

        if encrypted_start:
            encrypted_str += out.split("Encryption successful")[0]

    if encrypted_successful_found and encrypted_start:
        return encrypted_str
    else:
        raise AnsibleVaultEncryptionFailed("Failed to encrypt string")


def decrypt(password: str, vault_string: str) -> str:
    child = pexpect.spawn("ansible-vault decrypt")
    child.expect("Vault password: ")
    child.sendline(password)
    child.expect("Reading ciphertext input from stdin")
    child.sendline(vault_string)
    child.sendcontrol("D")
    i = child.expect(["Decryption successful", "ERROR"])
    if i == 0:
        return "".join(line.decode() for line in child).strip()
    else:
        error_msg = child.readline()
        raise AnsibleVaultDecryptionFailed(error_msg.decode())
