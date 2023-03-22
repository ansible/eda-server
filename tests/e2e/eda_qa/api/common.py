import logging
import typing
from typing import Iterator
from typing import TYPE_CHECKING

from eda_api.exceptions import ApiException

# avoiding circular import, only for typing purposes
if TYPE_CHECKING:
    from eda_qa.api.client import ApiClient


LOGGER = logging.getLogger("edaqa_api")

C = typing.TypeVar("C", bound="Response")


class Response:
    """
    Stores the wrapped response from the openapi-client response
    """

    status_code: typing.Optional[int]
    data: typing.Any

    def __str__(self) -> str:
        return f"{self.__class__}: status_code: {self.status_code}, data: {type(self.data)}"

    def __repr__(self) -> str:
        return f"{self.__class__}: status_code: {self.status_code}, data: {type(self.data)}"

    def __init__(self, status_code=None, data=None):
        self.status_code = status_code
        self.data = data

    @classmethod
    def from_response(cls: type[C], response: tuple) -> C:
        return cls(data=response[0], status_code=response[1])

    @classmethod
    def from_exception(cls: type[C], response: ApiException) -> C:
        return cls(status_code=response.status, data=response.body)


class BaseApi:
    """
    Base class to wrap openapi api's. All wrappers should inherit from this class.
    Implements client instantiation from the children as well as wraps the request and response
    Exposes the api_client to all children
    """

    api: typing.Callable

    def __init__(self, api_client: "ApiClient"):
        self.api_client = api_client
        self.client = api_client.openapi_client
        self.api_instance = self.api(self.client)

    def run(self, operation: str, *args, **kwargs) -> Response:
        caller = getattr(self.api_instance, operation)
        try:
            LOGGER.info(f"Running request '{operation}' with args {args} - {kwargs}")
            response = caller(_return_http_data_only=False, *args, **kwargs)
            response = Response.from_response(response)
        except ApiException as e:
            LOGGER.info(
                f"Request {operation} failed with status code: {e.status}, response: {e.body}"
            )
            response = Response.from_exception(e)

        return response

    def iter_pages(self) -> Iterator[Response]:
        """
        Common method to iterate over all available pages.
        """
        if not hasattr(self, "list"):
            raise AttributeError(f"{self.__class__.__name__} has not list method")
        next_page = True
        page = 1
        while next_page:
            response = self.list(page=page)
            next_page = response.data.next
            page = response.data.page + 1
            yield response


class CaseInsensitiveString(str):
    def __eq__(self, other):
        return self.lower() == other.lower()
