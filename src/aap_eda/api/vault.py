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
    tmp = tempfile.NamedTemporaryFile("w+t")
    tmp.write(password)
    tmp.flush()
    label = f"{vault_id}@{tmp.name}"

    child = pexpect.spawn(f"ansible-vault encrypt_string --vault-id {label}")
    child.expect("Reading plaintext input from stdin*")
    child.sendline(plaintext)
    child.sendcontrol("D")
    i = child.expect(["Encryption successful", "ERROR"])
    if i == 0:
        child.readline()
        return "".join(
            line.decode().lstrip()
            for line in child
            if not line.decode().startswith("!vault")
        )
    else:
        error_msg = child.readline()
        raise AnsibleVaultEncryptionFailed(error_msg)


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
