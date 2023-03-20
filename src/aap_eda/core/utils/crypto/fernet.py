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
import base64
import binascii
from typing import Optional, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.utils.encoding import force_bytes


def get_encryption_key(
    length: int,
    salt: Union[str, bytes, None] = None,
    info: Union[str, bytes, None] = None,
    key_material: Optional[str] = None,
) -> bytes:
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    )
    key_material = key_material or settings.SECRET_KEY
    derived_key = kdf.derive(force_bytes(key_material))
    return base64.urlsafe_b64encode(derived_key)


class Fernet256(Fernet):
    """Fernet-like schema based on AES-256 encryption.

    Not technically Fernet, but uses the base of the Fernet spec
    and uses AES-256-CBC instead of AES-128-CBC.
    All other functionality remain identical.
    """

    def __init__(self, key, backend=None):
        try:
            key = base64.urlsafe_b64decode(key)
        except binascii.Error as exc:
            raise ValueError(
                "Fernet key must be 64 url-safe base64-encoded bytes."
            ) from exc
        if len(key) != 64:
            raise ValueError(
                "Fernet key must be 64 url-safe base64-encoded bytes."
            )

        self._signing_key = key[:32]
        self._encryption_key = key[32:]
