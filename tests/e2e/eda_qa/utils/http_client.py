"""
Standard http client
"""
import atexit

import httpx


def get_http_client() -> httpx.Client:
    headers = {"user-agent": "eda-qa"}
    http_client = httpx.Client(headers=headers)
    atexit.register(http_client.close)
    return http_client
