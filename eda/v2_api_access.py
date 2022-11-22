from awx.main.access import BaseAccess, access_registry

from eda.models import ActivationInstanceJobInstance
from eda.models import ActivationInstance
from eda.models import ExtraVar
from eda.models import Project
from eda.models import Inventory
from eda.models import Rulebook
from eda.models import JobInstance
from eda.models import ActivationInstanceLog
from eda.models import Rule
from eda.models import Ruleset
from eda.models import Job
from eda.models import Playbook
from eda.models import AuditRule
from eda.models import JobInstanceEvent
from eda.models import JobInstanceHost
from eda.models import Activation
from eda.models import Role
from eda.models import RolePermission
from eda.models import UserRole
from eda.models import User


class ActivationInstanceJobInstanceAccess(BaseAccess):

    model = ActivationInstanceJobInstance


access_registry[ActivationInstanceJobInstance] = ActivationInstanceJobInstanceAccess


class ActivationInstanceAccess(BaseAccess):

    model = ActivationInstance


access_registry[ActivationInstance] = ActivationInstanceAccess


class ExtraVarAccess(BaseAccess):

    model = ExtraVar


access_registry[ExtraVar] = ExtraVarAccess


class ProjectAccess(BaseAccess):

    model = Project


access_registry[Project] = ProjectAccess


class InventoryAccess(BaseAccess):

    model = Inventory


access_registry[Inventory] = InventoryAccess


class RulebookAccess(BaseAccess):

    model = Rulebook


access_registry[Rulebook] = RulebookAccess


class JobInstanceAccess(BaseAccess):

    model = JobInstance


access_registry[JobInstance] = JobInstanceAccess


class ActivationInstanceLogAccess(BaseAccess):

    model = ActivationInstanceLog


access_registry[ActivationInstanceLog] = ActivationInstanceLogAccess


class RuleAccess(BaseAccess):

    model = Rule


access_registry[Rule] = RuleAccess


class RulesetAccess(BaseAccess):

    model = Ruleset


access_registry[Ruleset] = RulesetAccess


class JobAccess(BaseAccess):

    model = Job


access_registry[Job] = JobAccess


class PlaybookAccess(BaseAccess):

    model = Playbook


access_registry[Playbook] = PlaybookAccess


class AuditRuleAccess(BaseAccess):

    model = AuditRule


access_registry[AuditRule] = AuditRuleAccess


class JobInstanceEventAccess(BaseAccess):

    model = JobInstanceEvent


access_registry[JobInstanceEvent] = JobInstanceEventAccess


class JobInstanceHostAccess(BaseAccess):

    model = JobInstanceHost


access_registry[JobInstanceHost] = JobInstanceHostAccess


class ActivationAccess(BaseAccess):

    model = Activation


access_registry[Activation] = ActivationAccess


class RoleAccess(BaseAccess):

    model = Role


access_registry[Role] = RoleAccess


class RolePermissionAccess(BaseAccess):

    model = RolePermission


access_registry[RolePermission] = RolePermissionAccess


class UserRoleAccess(BaseAccess):

    model = UserRole


access_registry[UserRole] = UserRoleAccess


class UserAccess(BaseAccess):

    model = User


access_registry[User] = UserAccess
