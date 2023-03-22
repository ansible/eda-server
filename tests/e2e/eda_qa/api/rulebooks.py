import typing

import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import Response
from eda_qa.api.utils import filter_by_name
from eda_qa.config import config


class RulebooksApi(BaseApi):
    """
    Wraps the openapi api for rulebooks endpoint
    """

    api = apis.RulebooksApi

    def read(self, rulebook_id: int, **kwargs) -> Response:
        """
        Retrieves a rulebook
        """
        operation = "rulebooks_retrieve"
        return self.run(operation, rulebook_id, **kwargs)

    def list(self, **kwargs) -> Response:  # noqa: A003
        """
        List rulebooks
        """
        operation = "rulebooks_list"
        return self.run(operation, **kwargs)

    def get_by_name(self, name: str) -> typing.Optional[dict]:
        """
        Get the rulebook by given name, return None if is not found
        """
        # TODO: Refactor to iterate over pages
        # Use filter when is implemented.
        response = self.list()
        return filter_by_name(response.data, name)

    def get_default_rulebook(self) -> dict:
        """
        Get the default rulebook, returns an Exception if is not found
        """
        rulebook = self.get_by_name(config.default_rulebook)  # type: ignore comment;

        if not rulebook:
            raise Exception("Default rulebook not found")

        return rulebook
