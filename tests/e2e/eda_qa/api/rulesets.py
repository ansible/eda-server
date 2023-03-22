import typing

import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import Response
from eda_qa.api.utils import filter_by_name
from eda_qa.config import config


class RulesetsApi(BaseApi):
    """
    Wraps the openapi api for rulesets endpoints
    """

    api = apis.RulesetsApi

    def read(self, ruleset_id: int, **kwargs) -> Response:
        """
        Retrieves a ruleset
        """
        operation = "rulesets_retrieve"
        return self.run(operation, ruleset_id, **kwargs)

    def list(self, **kwargs) -> Response:  # noqa: A003
        """
        List rulesets
        """
        operation = "rulesets_list"
        return self.run(operation, **kwargs)

    def get_by_name(self, name: str) -> typing.Optional[dict]:
        """
        Get the rulebook by given name, return None if is not found
        """
        response = self.list()
        return filter_by_name(response.data, name)

    def get_default_ruleset(self) -> dict:
        """
        Get the default ruleset, returns an Exception if is not found
        """
        rulebook = self.get_by_name(config.default_ruleset)  # type: ignore comment;

        if not rulebook:
            raise Exception("Default ruleset not found")

        return rulebook
