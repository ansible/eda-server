import typing

from eda_qa.api.client import ApiClient
from eda_qa.api.client import Configuration
from eda_qa.config import config
from eda_qa.exceptions import AuthError

# not implemented yet
# from eda_qa.api.auth import BearerTokenAuth # noqa: E800


def get_api_client(user_profile: typing.Optional[str] = None) -> ApiClient:
    """
    Api client factory. Only basic auth is supported for now.
    """
    # Set user
    user_data = config.users.get(config.default_user)
    if user_profile is not None:
        user_data = config.users.get(user_profile)

    # set auth method
    auth_method = user_data.get("auth_method", config.get("default_auth_method"))

    if auth_method == "basicauth":
        api_config = Configuration(username=user_data.username, password=user_data.password)
    else:
        raise AuthError("No auth method defined")

    return ApiClient(api_config=api_config)


# default api client
api_client = get_api_client()
