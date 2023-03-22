from typing import Any


class BaseModel:
    """
    Base model to extend openapi models
    """

    def __init__(self, _obj) -> None:
        self._obj = _obj

    def __getattr__(self, name) -> Any:
        return self._obj.__getattr__(name)
