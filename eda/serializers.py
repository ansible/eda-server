from rest_framework.serializers import ModelSerializer

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
            "project_id",
            "activation",
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
