
# flake8: noqa

# Import all APIs into this package.
# If you have many APIs here with many many models used in each API this may
# raise a `RecursionError`.
# In order to avoid this, import only the API that you directly need like:
#
#   from eda_api.api.activation_instances_api import ActivationInstancesApi
#
# or import this package, but before doing it, use:
#
#   import sys
#   sys.setrecursionlimit(n)

# Import APIs into API package:
from eda_api.api.activation_instances_api import ActivationInstancesApi
from eda_api.api.activations_api import ActivationsApi
from eda_api.api.auth_api import AuthApi
from eda_api.api.extra_vars_api import ExtraVarsApi
from eda_api.api.playbooks_api import PlaybooksApi
from eda_api.api.projects_api import ProjectsApi
from eda_api.api.rulebooks_api import RulebooksApi
from eda_api.api.rules_api import RulesApi
from eda_api.api.rulesets_api import RulesetsApi
from eda_api.api.tasks_api import TasksApi
from eda_api.api.users_api import UsersApi
