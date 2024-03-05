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

from django.db import models

from aap_eda.core.enums import CredentialType
from aap_eda.core.utils.crypto.fields import EncryptedTextField

__all__ = ("Credential",)


class Credential(models.Model):
    class Meta:
        db_table = "core_credential"
        constraints = [
            # This applies to all credentials.
            models.CheckConstraint(
                name="ck_empty_credential_name",
                check=~models.Q(name=""),
            ),
            # This applies to non-SCM credentials.
            models.CheckConstraint(
                name="ck_empty_secret",
                check=(
                    models.Q(credential_type=CredentialType.SCM)
                    | (models.Q(secret__isnull=False) & ~models.Q(secret=""))
                ),
            ),
            # This applies only to SCM credentials.
            # User/secret is the scm user/password.
            models.CheckConstraint(
                name="ck_scm_credential",
                check=(
                    ~models.Q(credential_type=CredentialType.SCM)
                    | (
                        # There are three basic valid scenarios:
                        #   1. a secret by itself
                        #   2. a secret with a username
                        #   3. an ssh key with a password
                        # Additionally, #3 can be combined with #1 or #2.
                        (
                            (
                                models.Q(scm_ssh_key__isnull=True)
                                | models.Q(scm_ssh_key="")
                            )
                            & (
                                models.Q(scm_ssh_key_passphrase__isnull=True)
                                | models.Q(scm_ssh_key_passphrase="")
                            )
                            & (
                                models.Q(secret__isnull=False)
                                & ~models.Q(secret="")
                            )
                        )
                        | (
                            (
                                models.Q(scm_ssh_key__isnull=False)
                                & ~models.Q(scm_ssh_key="")
                            )
                            & (
                                models.Q(scm_ssh_key_passphrase__isnull=False)
                                & ~models.Q(scm_ssh_key_passphrase="")
                            )
                        )
                    )
                ),
            ),
        ]

    name = models.TextField(null=False, unique=True)
    description = models.TextField(default="", blank=True, null=False)
    credential_type = models.TextField(
        choices=CredentialType.choices(),
        default=CredentialType.REGISTRY,
    )
    username = models.TextField(null=True)
    secret = EncryptedTextField(null=True)
    vault_identifier = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    modified_at = models.DateTimeField(auto_now=True, null=False)

    scm_ssh_key = EncryptedTextField(null=True)
    scm_ssh_key_passphrase = EncryptedTextField(null=True)
