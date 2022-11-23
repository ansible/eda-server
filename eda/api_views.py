import json

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
from eda.serializers import (
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

    queryset = ActivationInstanceJobInstance.objects.all()
    serializer_class = ActivationInstanceJobInstanceSerializer


class ActivationInstanceJobInstanceDetail(RetrieveUpdateDestroyAPIView):

    queryset = ActivationInstanceJobInstance.objects.all()
    serializer_class = ActivationInstanceJobInstanceSerializer


class ActivationInstanceList(ListCreateAPIView):

    queryset = ActivationInstance.objects.all()
    serializer_class = ActivationInstanceSerializer


class ActivationInstanceDetail(RetrieveUpdateDestroyAPIView):

    queryset = ActivationInstance.objects.all()
    serializer_class = ActivationInstanceSerializer


class ExtraVarList(ListCreateAPIView):

    queryset = ExtraVar.objects.all()
    serializer_class = ExtraVarSerializer


class ExtraVarDetail(RetrieveUpdateDestroyAPIView):

    queryset = ExtraVar.objects.all()
    serializer_class = ExtraVarSerializer


class ProjectList(ListCreateAPIView):

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class ProjectDetail(RetrieveUpdateDestroyAPIView):

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class InventoryList(ListCreateAPIView):

    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer


class InventoryDetail(RetrieveUpdateDestroyAPIView):

    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer


class RulebookList(ListCreateAPIView):

    queryset = Rulebook.objects.all()
    serializer_class = RulebookSerializer


class RulebookDetail(RetrieveUpdateDestroyAPIView):

    queryset = Rulebook.objects.all()
    serializer_class = RulebookSerializer


class JobInstanceList(ListCreateAPIView):

    queryset = JobInstance.objects.all()
    serializer_class = JobInstanceSerializer


class JobInstanceDetail(RetrieveUpdateDestroyAPIView):

    queryset = JobInstance.objects.all()
    serializer_class = JobInstanceSerializer


class ActivationInstanceLogList(ListCreateAPIView):

    queryset = ActivationInstanceLog.objects.all()
    serializer_class = ActivationInstanceLogSerializer


class ActivationInstanceLogDetail(RetrieveUpdateDestroyAPIView):

    queryset = ActivationInstanceLog.objects.all()
    serializer_class = ActivationInstanceLogSerializer


class RuleList(ListCreateAPIView):

    queryset = Rule.objects.all()
    serializer_class = RuleSerializer


class RuleDetail(RetrieveUpdateDestroyAPIView):

    queryset = Rule.objects.all()
    serializer_class = RuleSerializer


class RulesetList(ListCreateAPIView):

    queryset = Ruleset.objects.all()
    serializer_class = RulesetSerializer


class RulesetDetail(RetrieveUpdateDestroyAPIView):

    queryset = Ruleset.objects.all()
    serializer_class = RulesetSerializer


class JobList(ListCreateAPIView):

    queryset = Job.objects.all()
    serializer_class = JobSerializer


class JobDetail(RetrieveUpdateDestroyAPIView):

    queryset = Job.objects.all()
    serializer_class = JobSerializer


class PlaybookList(ListCreateAPIView):

    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer


class PlaybookDetail(RetrieveUpdateDestroyAPIView):

    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer


class AuditRuleList(ListCreateAPIView):

    queryset = AuditRule.objects.all()
    serializer_class = AuditRuleSerializer


class AuditRuleDetail(RetrieveUpdateDestroyAPIView):

    queryset = AuditRule.objects.all()
    serializer_class = AuditRuleSerializer


class JobInstanceEventList(ListCreateAPIView):

    queryset = JobInstanceEvent.objects.all()
    serializer_class = JobInstanceEventSerializer


class JobInstanceEventDetail(RetrieveUpdateDestroyAPIView):

    queryset = JobInstanceEvent.objects.all()
    serializer_class = JobInstanceEventSerializer


class JobInstanceHostList(ListCreateAPIView):

    queryset = JobInstanceHost.objects.all()
    serializer_class = JobInstanceHostSerializer


class JobInstanceHostDetail(RetrieveUpdateDestroyAPIView):

    queryset = JobInstanceHost.objects.all()
    serializer_class = JobInstanceHostSerializer


class ActivationList(ListCreateAPIView):

    queryset = Activation.objects.all()
    serializer_class = ActivationSerializer


class ActivationDetail(RetrieveUpdateDestroyAPIView):

    queryset = Activation.objects.all()
    serializer_class = ActivationSerializer


class RoleList(ListCreateAPIView):

    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class RoleDetail(RetrieveUpdateDestroyAPIView):

    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class RolePermissionList(ListCreateAPIView):

    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer


class RolePermissionDetail(RetrieveUpdateDestroyAPIView):

    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer


class UserRoleList(ListCreateAPIView):

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer


class UserRoleDetail(RetrieveUpdateDestroyAPIView):

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer


class UserList(ListCreateAPIView):

    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(RetrieveUpdateDestroyAPIView):

    queryset = User.objects.all()
    serializer_class = UserSerializer
