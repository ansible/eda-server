from awx.main.access import BaseAccess, access_registry

from .models import ActivationInstanceJobInstance
from .models import ActivationInstance
from .models import ExtraVar
from .models import Project
from .models import Inventory
from .models import Rulebook
from .models import JobInstance
from .models import ActivationInstanceLog
from .models import Rule
from .models import Ruleset
from .models import Job
from .models import Playbook
from .models import AuditRule
from .models import JobInstanceEvent
from .models import JobInstanceHost
from .models import Activation
from .models import Role
from .models import RolePermission
from .models import UserRole
from .models import User


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
