"""
Module for edaqa cli tool
"""
import argparse

from cryptography.fernet import Fernet

from eda_qa.config import config
from eda_qa.utils.fernet import decrypt


def parse_args():
    parser = argparse.ArgumentParser(description="Cli tool for ansible events QE test suite")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--encrypt", type=str, action="store", help="encrypt string")

    group.add_argument("--decrypt", type=str, action="store", help="decrypt string")

    return parser.parse_args()


def get_fernet_password():
    password = config.get("fernet_password", None)
    if password is None:
        return Exception("EDAQA_FERNET_PASSWORD environment variable is not defined")
    return password


def _decrypt(key: str, data: str) -> None:
    print(decrypt(key, data))
    raise SystemExit


def _encrypt(key: str, data: str) -> None:
    fernet = Fernet(key)
    dec = fernet.encrypt(data.encode())
    print(dec.decode())
    raise SystemExit


def main():
    args = parse_args()
    if args.decrypt:
        _decrypt(get_fernet_password(), args.decrypt)
    if args.encrypt:
        _encrypt(get_fernet_password(), args.encrypt)
