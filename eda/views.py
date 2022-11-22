import json
import channels
from utils import transform_dict

from rest_framework.generics import ListCreateAPIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from eda.models import (
    ActivationInstanceJobInstance,
    ActivationInstance,
    ExtraVar,
    Project,
    Inventory,
    Rulebook,
    JobInstance,
    ActivationInstanceLog,
    Rule,
    Ruleset,
    Job,
    Playbook,
    AuditRule,
    JobInstanceEvent,
    JobInstanceHost,
    Activation,
    Role,
    RolePermission,
    UserRole,
    User,
)
from eda.v2_api_serializers import (
    ActivationInstanceJobInstanceSerializer,
    ActivationInstanceSerializer,
    ExtraVarSerializer,
    ProjectSerializer,
    InventorySerializer,
    RulebookSerializer,
    JobInstanceSerializer,
    ActivationInstanceLogSerializer,
    RuleSerializer,
    RulesetSerializer,
    JobSerializer,
    PlaybookSerializer,
    AuditRuleSerializer,
    JobInstanceEventSerializer,
    JobInstanceHostSerializer,
    ActivationSerializer,
    RoleSerializer,
    RolePermissionSerializer,
    UserRoleSerializer,
    UserSerializer,
)


class ActivationInstanceJobInstanceList(ListCreateAPIView):

    model = ActivationInstanceJobInstance
    serializer_class = ActivationInstanceJobInstanceSerializer


class ActivationInstanceJobInstanceDetail(RetrieveUpdateDestroyAPIView):

    model = ActivationInstanceJobInstance
    serializer_class = ActivationInstanceJobInstanceSerializer


class ActivationInstanceList(ListCreateAPIView):

    model = ActivationInstance
    serializer_class = ActivationInstanceSerializer


class ActivationInstanceDetail(RetrieveUpdateDestroyAPIView):

    model = ActivationInstance
    serializer_class = ActivationInstanceSerializer


class ExtraVarList(ListCreateAPIView):

    model = ExtraVar
    serializer_class = ExtraVarSerializer


class ExtraVarDetail(RetrieveUpdateDestroyAPIView):

    model = ExtraVar
    serializer_class = ExtraVarSerializer


class ProjectList(ListCreateAPIView):

    model = Project
    serializer_class = ProjectSerializer


class ProjectDetail(RetrieveUpdateDestroyAPIView):

    model = Project
    serializer_class = ProjectSerializer


class InventoryList(ListCreateAPIView):

    model = Inventory
    serializer_class = InventorySerializer


class InventoryDetail(RetrieveUpdateDestroyAPIView):

    model = Inventory
    serializer_class = InventorySerializer


class RulebookList(ListCreateAPIView):

    model = Rulebook
    serializer_class = RulebookSerializer


class RulebookDetail(RetrieveUpdateDestroyAPIView):

    model = Rulebook
    serializer_class = RulebookSerializer


class JobInstanceList(ListCreateAPIView):

    model = JobInstance
    serializer_class = JobInstanceSerializer


class JobInstanceDetail(RetrieveUpdateDestroyAPIView):

    model = JobInstance
    serializer_class = JobInstanceSerializer


class ActivationInstanceLogList(ListCreateAPIView):

    model = ActivationInstanceLog
    serializer_class = ActivationInstanceLogSerializer


class ActivationInstanceLogDetail(RetrieveUpdateDestroyAPIView):

    model = ActivationInstanceLog
    serializer_class = ActivationInstanceLogSerializer


class RuleList(ListCreateAPIView):

    model = Rule
    serializer_class = RuleSerializer


class RuleDetail(RetrieveUpdateDestroyAPIView):

    model = Rule
    serializer_class = RuleSerializer


class RulesetList(ListCreateAPIView):

    model = Ruleset
    serializer_class = RulesetSerializer


class RulesetDetail(RetrieveUpdateDestroyAPIView):

    model = Ruleset
    serializer_class = RulesetSerializer


class JobList(ListCreateAPIView):

    model = Job
    serializer_class = JobSerializer


class JobDetail(RetrieveUpdateDestroyAPIView):

    model = Job
    serializer_class = JobSerializer


class PlaybookList(ListCreateAPIView):

    model = Playbook
    serializer_class = PlaybookSerializer


class PlaybookDetail(RetrieveUpdateDestroyAPIView):

    model = Playbook
    serializer_class = PlaybookSerializer


class AuditRuleList(ListCreateAPIView):

    model = AuditRule
    serializer_class = AuditRuleSerializer


class AuditRuleDetail(RetrieveUpdateDestroyAPIView):

    model = AuditRule
    serializer_class = AuditRuleSerializer


class JobInstanceEventList(ListCreateAPIView):

    model = JobInstanceEvent
    serializer_class = JobInstanceEventSerializer


class JobInstanceEventDetail(RetrieveUpdateDestroyAPIView):

    model = JobInstanceEvent
    serializer_class = JobInstanceEventSerializer


class JobInstanceHostList(ListCreateAPIView):

    model = JobInstanceHost
    serializer_class = JobInstanceHostSerializer


class JobInstanceHostDetail(RetrieveUpdateDestroyAPIView):

    model = JobInstanceHost
    serializer_class = JobInstanceHostSerializer


class ActivationList(ListCreateAPIView):

    model = Activation
    serializer_class = ActivationSerializer


class ActivationDetail(RetrieveUpdateDestroyAPIView):

    model = Activation
    serializer_class = ActivationSerializer


class RoleList(ListCreateAPIView):

    model = Role
    serializer_class = RoleSerializer


class RoleDetail(RetrieveUpdateDestroyAPIView):

    model = Role
    serializer_class = RoleSerializer


class RolePermissionList(ListCreateAPIView):

    model = RolePermission
    serializer_class = RolePermissionSerializer


class RolePermissionDetail(RetrieveUpdateDestroyAPIView):

    model = RolePermission
    serializer_class = RolePermissionSerializer


class UserRoleList(ListCreateAPIView):

    model = UserRole
    serializer_class = UserRoleSerializer


class UserRoleDetail(RetrieveUpdateDestroyAPIView):

    model = UserRole
    serializer_class = UserRoleSerializer


class UserList(ListCreateAPIView):

    model = User
    serializer_class = UserSerializer


class UserDetail(RetrieveUpdateDestroyAPIView):

    model = User
    serializer_class = UserSerializer
