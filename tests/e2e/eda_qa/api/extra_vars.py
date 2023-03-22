import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import Response


class ExtraVarsApi(BaseApi):
    """
    Wraps the openapi api for extra_vars endpoint
    """

    api = apis.ExtraVarsApi

    def read(self, extra_vars_id: int, **kwargs) -> Response:
        """
        Retrieves an extra_vars instance
        """
        operation = "extra_vars_retrieve"
        return self.run(operation, extra_vars_id, **kwargs)
