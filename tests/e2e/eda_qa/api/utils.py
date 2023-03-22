from typing import Optional


def filter_by_name(items: list[dict], name: str) -> Optional[dict]:
    """
    Receives a list a return the dict with the given name of None.
    TODO: This helper must be replaced with proper filtering in list endpoints.
    """
    result = None
    for item in items:
        if item["name"] == name:
            result = item
            break
    return result
