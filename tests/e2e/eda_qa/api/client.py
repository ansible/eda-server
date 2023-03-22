"""
Module for custom implementation of the api client
"""
import logging
import typing
from functools import cached_property

from eda_api.api_client import ApiClient as OpenApiClient
from eda_api.configuration import (
    Configuration as OpenApiConfiguration,
)
from eda_qa.api.activations import ActivationsApi
from eda_qa.api.extra_vars import ExtraVarsApi
from eda_qa.api.projects import ProjectsApi
from eda_qa.api.rulebooks import RulebooksApi
from eda_qa.api.rules import RulesApi
from eda_qa.api.rulesets import RulesetsApi
from eda_qa.api.tasks import TasksApi
from eda_qa.config import config

# Not implemented in the api yet
# from eda_qa.api.users import AuthApi # noqa: E800
# from eda_qa.api.users import CurrentUserApi # noqa: E800

LOGGER = logging.getLogger("edaqa_api")


class Configuration(OpenApiConfiguration):
    """
    Custom implementation of client library configuration.
    Overrides some attributes for auth management and http config
    """

    def __init__(self, auth_backend=None, config=config, *args, **kwargs):
        self._access_token = None
        host = config.base_url
        self._auth_backend = auth_backend
        super().__init__(host=host, *args, **kwargs)
        self.verify_ssl = config.http.verify_ssl  # type: ignore comment;


A = typing.TypeVar("A", bound="ApiClient")


class ApiClient:
    """
    Wraps the Openapi api client, provides instantiations for path groups
    """

    def __init__(self, api_config) -> None:
        self.openapi_client = OpenApiClient(api_config)

    # Not implemented in the api yet
    # @cached_property
    # def auth(self):
    #     return AuthApi(self) # noqa: E800

    @cached_property
    def projects(self):
        return ProjectsApi(self)

    # Not implemented in the api yet
    # @cached_property
    # def current_user(self):
    #     return CurrentUserApi(self) # noqa: E800

    @cached_property
    def rules(self):
        return RulesApi(self)

    @cached_property
    def rulebooks(self):
        return RulebooksApi(self)

    @cached_property
    def extra_vars(self):
        return ExtraVarsApi(self)

    @cached_property
    def activations(self):
        return ActivationsApi(self)

    @cached_property
    def rulesets(self):
        return RulesetsApi(self)

    @cached_property
    def tasks(self):
        return TasksApi(self)
