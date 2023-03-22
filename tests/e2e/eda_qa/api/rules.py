"""
rules api
"""
import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import Response


class RulesApi(BaseApi):
    """
    Wraps the openapi api for projects endpoints
    """

    api = apis.RulesApi

    def list(self, *args, **kwargs) -> Response:  # noqa: A003
        operation = "rules_list"
        return self.run(operation, *args, **kwargs)

    def read(self, rule_id, *args, **kwargs):
        operation = "rules_retrieve"
        return self.run(operation, rule_id, *args, **kwargs)
