"""
Module for encryted data
Uses cryptography.fernet to encrypt configuration values.

Fernet is simmetric encryption based on AES cipher
More info: https://cryptography.io/en/latest/fernet/
"""
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache
def decrypt(key: str, data: str) -> str:
    """
    Receives a key and some data encrypted and returns a string decrypted
    """
    fernet = Fernet(key)
    enc = fernet.decrypt(data.encode())
    return enc.decode()
