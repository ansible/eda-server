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

import logging

from cryptography.fernet import InvalidToken

from aap_eda.core import models

LOGGER = logging.getLogger(__name__)


def check_encryption_key() -> None:
    """Check the decryption of credentials.

    Try to decrypt the first credential in the database.
    If it fails, raise an exception.
    """
    try:
        first_credential = models.Credential.objects.first()
    except InvalidToken as exc:
        msg = "Failed to decrypt credentials, secret key may be incorrect."
        LOGGER.exception(msg)
        raise RuntimeError(msg) from exc

    if not first_credential:
        LOGGER.info("No credentials found in the database.")
        return

    LOGGER.info("Credentials decrypted successfully.")
