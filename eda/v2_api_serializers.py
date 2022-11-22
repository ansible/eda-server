from restframework.serializers import ModelSerializer

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


class AlembicVersionSerializer(ModelSerializer):
    class Meta:
        model = AlembicVersion
        fields = "version_num"


class ActivationInstanceJobInstanceSerializer(ModelSerializer):
    class Meta:
        model = ActivationInstanceJobInstance
        fields = ("id", "activation_instance_id", "job_instance_id")


class ActivationInstanceSerializer(ModelSerializer):
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


class ExtraVarSerializer(ModelSerializer):
    class Meta:
        model = ExtraVar
        fields = ("id", "name", "extra_var", "project_id")


class ProjectSerializer(ModelSerializer):
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


class InventorySerializer(ModelSerializer):
    class Meta:
        model = Inventory
        fields = ("id", "name", "inventory", "project_id")


class RulebookSerializer(ModelSerializer):
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


class JobInstanceSerializer(ModelSerializer):
    class Meta:
        model = JobInstance
        fields = ("id", "uuid")


class ActivationInstanceLogSerializer(ModelSerializer):
    class Meta:
        model = ActivationInstanceLog
        fields = ("id", "activation_instance_id", "line_number", "log")


class RuleSerializer(ModelSerializer):
    class Meta:
        model = Rule
        fields = ("id", "ruleset_id", "name", "action")


class RulesetSerializer(ModelSerializer):
    class Meta:
        model = Ruleset
        fields = ("id", "rulebook_id", "name", "created_at", "modified_at")


class JobSerializer(ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "uuid")


class PlaybookSerializer(ModelSerializer):
    class Meta:
        model = Playbook
        fields = ("id", "name", "playbook", "project_id")


class AuditRuleSerializer(ModelSerializer):
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


class JobInstanceEventSerializer(ModelSerializer):
    class Meta:
        model = JobInstanceEvent
        fields = ("id", "job_uuid", "counter", "stdout", "type", "created_at")


class JobInstanceHostSerializer(ModelSerializer):
    class Meta:
        model = JobInstanceHost
        fields = ("id", "host", "job_uuid", "playbook", "play", "task", "status")


class ActivationSerializer(ModelSerializer):
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


class RoleSerializer(ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "description")


class RolePermissionSerializer(ModelSerializer):
    class Meta:
        model = RolePermission
        fields = ("id", "role_id", "resource_type", "action")


class UserRoleSerializer(ModelSerializer):
    class Meta:
        model = UserRole
        fields = ("user_id", "role_id", "id")


class UserSerializer(ModelSerializer):
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
