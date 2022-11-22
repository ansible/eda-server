from awx.api.serializers import BaseSerializer

from .models import AlembicVersion
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


class AlembicVersionSerializer(BaseSerializer):
    class Meta:
        model = AlembicVersion
        fields = "version_num"


class ActivationInstanceJobInstanceSerializer(BaseSerializer):
    class Meta:
        model = ActivationInstanceJobInstance
        fields = ("id", "activation_instance_id", "job_instance_id")


class ActivationInstanceSerializer(BaseSerializer):
    class Meta:
        model = ActivationInstance
        fields = (
            "id",
            "name",
            "rulebook_id",
            "inventory_id",
            "extra_var_id",
            "execution_environment",
            "working_directory",
            "large_data_id",
            "project_id",
        )


class ExtraVarSerializer(BaseSerializer):
    class Meta:
        model = ExtraVar
        fields = ("id", "name", "extra_var", "project_id")


class ProjectSerializer(BaseSerializer):
    class Meta:
        model = Project
        fields = (
            "id",
            "git_hash",
            "url",
            "name",
            "description",
            "created_at",
            "modified_at",
            "large_data_id",
        )


class InventorySerializer(BaseSerializer):
    class Meta:
        model = Inventory
        fields = ("id", "name", "inventory", "project_id")


class RulebookSerializer(BaseSerializer):
    class Meta:
        model = Rulebook
        fields = (
            "id",
            "name",
            "rulesets",
            "project_id",
            "description",
            "created_at",
            "modified_at",
        )


class JobInstanceSerializer(BaseSerializer):
    class Meta:
        model = JobInstance
        fields = ("id", "uuid")


class ActivationInstanceLogSerializer(BaseSerializer):
    class Meta:
        model = ActivationInstanceLog
        fields = ("id", "activation_instance_id", "line_number", "log")


class RuleSerializer(BaseSerializer):
    class Meta:
        model = Rule
        fields = ("id", "ruleset_id", "name", "action")


class RulesetSerializer(BaseSerializer):
    class Meta:
        model = Ruleset
        fields = ("id", "rulebook_id", "name", "created_at", "modified_at")


class JobSerializer(BaseSerializer):
    class Meta:
        model = Job
        fields = ("id", "uuid")


class PlaybookSerializer(BaseSerializer):
    class Meta:
        model = Playbook
        fields = ("id", "name", "playbook", "project_id")


class AuditRuleSerializer(BaseSerializer):
    class Meta:
        model = AuditRule
        fields = (
            "id",
            "name",
            "description",
            "status",
            "fired_date",
            "created_at",
            "definition",
            "rule_id",
            "ruleset_id",
            "activation_instance_id",
            "job_instance_id",
        )


class JobInstanceEventSerializer(BaseSerializer):
    class Meta:
        model = JobInstanceEvent
        fields = ("id", "job_uuid", "counter", "stdout", "type", "created_at")


class JobInstanceHostSerializer(BaseSerializer):
    class Meta:
        model = JobInstanceHost
        fields = ("id", "host", "job_uuid", "playbook", "play", "task", "status")


class ActivationSerializer(BaseSerializer):
    class Meta:
        model = Activation
        fields = (
            "id",
            "name",
            "rulebook_id",
            "inventory_id",
            "extra_var_id",
            "description",
            "status",
            "is_enabled",
            "restarted_at",
            "restart_count",
            "created_at",
            "modified_at",
            "working_directory",
            "execution_environment",
            "restart_policy",
        )


class RoleSerializer(BaseSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "description")


class RolePermissionSerializer(BaseSerializer):
    class Meta:
        model = RolePermission
        fields = ("id", "role_id", "resource_type", "action")


class UserRoleSerializer(BaseSerializer):
    class Meta:
        model = UserRole
        fields = ("user_id", "role_id")


class UserSerializer(BaseSerializer):
    class Meta:
        model = User
        fields = (
            "email",
            "hashed_password",
            "is_active",
            "is_superuser",
            "is_verified",
            "id",
        )
