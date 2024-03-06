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

from rest_framework import serializers

from aap_eda.api.constants import EDA_SERVER_VAULT_LABEL
from aap_eda.core import models
from aap_eda.core.enums import CredentialType


class CredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Credential
        read_only_fields = [
            "id",
            "created_at",
            "modified_at",
        ]
        fields = [
            "name",
            "description",
            "username",
            "credential_type",
            "vault_identifier",
            "scm_ssh_key",
            "scm_ssh_key_passphrase",
            *read_only_fields,
        ]


def _validate_scm_ssh_key_params(ssh_key, ssh_key_passphrase):
    """Both, or neither, of ssh key-related values must be specified."""
    if ((ssh_key is not None) and (ssh_key != "")) and (
        (ssh_key_passphrase is None) or (ssh_key_passphrase == "")
    ):
        raise serializers.ValidationError("missing scm key passphrase")

    if ((ssh_key is None) or (ssh_key == "")) and (
        (ssh_key_passphrase is not None) and (ssh_key_passphrase != "")
    ):
        raise serializers.ValidationError("missing scm key")


class CredentialCreateSerializer(serializers.ModelSerializer):
    def validate(self, data):
        credential_type = data.get("credential_type", CredentialType.REGISTRY)
        identifier = data.get("vault_identifier")

        if (
            credential_type == CredentialType.VAULT
            and identifier == EDA_SERVER_VAULT_LABEL
        ):
            raise serializers.ValidationError(
                f"{identifier} is reserved by EDA for vault labels"
            )

        if credential_type == CredentialType.SCM:
            # There are three basic valid scenarios:
            #   1. a secret by itself
            #   2. a secret with a username
            #   3. an ssh key with a passphrase
            # Additionally, #3 can be combined with #1 or #2.
            secret = data.get("secret", None)
            ssh_key = data.get("scm_ssh_key", None)
            ssh_key_passphrase = data.get("scm_ssh_key_passphrase", None)

            if (
                ((secret is None) or (secret == ""))
                and ((ssh_key is None) or (ssh_key == ""))
                and (
                    (ssh_key_passphrase is None) or (ssh_key_passphrase == "")
                )
            ):
                raise serializers.ValidationError(
                    "missing scm credential content"
                )

            _validate_scm_ssh_key_params(ssh_key, ssh_key_passphrase)

        return data

    class Meta:
        model = models.Credential
        fields = [
            "name",
            "description",
            "credential_type",
            "username",
            "secret",
            "vault_identifier",
            "scm_ssh_key",
            "scm_ssh_key_passphrase",
        ]


class CredentialPartialUpdateSerializer(serializers.ModelSerializer):
    def validate(self, data):
        ssh_key = data.get("scm_ssh_key", None)
        ssh_key_passphrase = data.get("scm_ssh_key_passphrase", None)

        _validate_scm_ssh_key_params(ssh_key, ssh_key_passphrase)

        return data

    class Meta:
        model = models.Credential
        fields = [
            "name",
            "description",
            "username",
            "secret",
            "vault_identifier",
            "scm_ssh_key",
            "scm_ssh_key_passphrase",
        ]


class CredentialRefSerializer(serializers.ModelSerializer):
    """Serializer for Credential reference."""

    class Meta:
        model = models.Credential
        fields = [
            "id",
            "name",
            "description",
            "credential_type",
            "username",
            "vault_identifier",
            "scm_ssh_key",
            "scm_ssh_key_passphrase",
        ]
        read_only_fields = ["id"]
