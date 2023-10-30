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
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.encoding import force_bytes

from .base import SecretValue
from .fernet import Fernet256, get_encryption_key

KEY_LENGTH = 64


def encrypt_string(value: str) -> str:
    fernet = Fernet256(get_encryption_key(KEY_LENGTH))
    encrypted_value = fernet.encrypt(force_bytes(value))
    tokens = ("$encrypted", "fernet-256", encrypted_value.decode("utf-8"))
    return "$".join(tokens)


def decrypt_string(value: str) -> str:
    tokens = value.split("$", 3)
    if tokens[0] != "" or tokens[1] != "encrypted":
        raise ValueError("Invalid encrypted string. Must start with $encrypted prefix.")
    if tokens[2] != "fernet-256":
        raise ValueError("Only fernet-256 is supported at the moment.")
    value = tokens[3]
    fernet = Fernet256(get_encryption_key(KEY_LENGTH))
    return fernet.decrypt(value).decode("utf-8")


class BaseEncryptedField(models.Field):
    def __init__(self, *args, **kwargs):
        if kwargs.get("primary_key"):
            raise ImproperlyConfigured(f"{self.__class__.__name__} does not support primary_key=True")
        if kwargs.get("unique"):
            raise ImproperlyConfigured(f"{self.__class__.__name__} does not support unique=True")
        if kwargs.get("db_index"):
            raise ImproperlyConfigured(f"{self.__class__.__name__} does not support db_index=True")

        super().__init__(*args, **kwargs)

    def get_internal_type(self):
        return "TextField"

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if "max_length" in kwargs:
            del kwargs["max_length"]
        return name, path, args, kwargs


class EncryptedTextField(BaseEncryptedField, models.TextField):
    def get_db_prep_save(self, value, connection):
        if value is None:
            return None
        if isinstance(value, SecretValue):
            value = value.get_secret_value()
        value = super().get_db_prep_save(value, connection)
        return encrypt_string(value)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return SecretValue(decrypt_string(value))


class EncryptedJsonField(BaseEncryptedField, models.JSONField):
    def get_db_prep_save(self, value, connection):
        if value is None:
            return None
        if isinstance(value, SecretValue):
            value = value.get_secret_value()
        value = super().get_db_prep_save(value, connection)
        return encrypt_string(value)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        value = decrypt_string(value)
        value = super().from_db_value(value, expression, connection)
        return SecretValue(value)
