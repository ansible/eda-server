import channels.layers
from asgiref.sync import async_to_sync

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

    def create(self, request, *args, **kwargs):
        response = super(ActivationInstanceJobInstanceList, self).create(
            request, *args, **kwargs
        )
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api",
            {"type": "create.ActivationInstanceJobInstance", "object": message},
        )
        return response


class ActivationInstanceJobInstanceDetail(RetrieveUpdateDestroyAPIView):

    queryset = ActivationInstanceJobInstance.objects.all()
    serializer_class = ActivationInstanceJobInstanceSerializer


class ActivationInstanceList(ListCreateAPIView):

    queryset = ActivationInstance.objects.all()
    serializer_class = ActivationInstanceSerializer

    def create(self, request, *args, **kwargs):
        response = super(ActivationInstanceList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.ActivationInstance", "object": message}
        )
        return response


class ActivationInstanceDetail(RetrieveUpdateDestroyAPIView):

    queryset = ActivationInstance.objects.all()
    serializer_class = ActivationInstanceSerializer


class ExtraVarList(ListCreateAPIView):

    queryset = ExtraVar.objects.all()
    serializer_class = ExtraVarSerializer

    def create(self, request, *args, **kwargs):
        response = super(ExtraVarList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.ExtraVar", "object": message}
        )
        return response


class ExtraVarDetail(RetrieveUpdateDestroyAPIView):

    queryset = ExtraVar.objects.all()
    serializer_class = ExtraVarSerializer


class ProjectList(ListCreateAPIView):

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def create(self, request, *args, **kwargs):
        response = super(ProjectList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Project", "object": message}
        )
        return response


class ProjectDetail(RetrieveUpdateDestroyAPIView):

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class InventoryList(ListCreateAPIView):

    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer

    def create(self, request, *args, **kwargs):
        response = super(InventoryList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Inventory", "object": message}
        )
        return response


class InventoryDetail(RetrieveUpdateDestroyAPIView):

    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer


class RulebookList(ListCreateAPIView):

    queryset = Rulebook.objects.all()
    serializer_class = RulebookSerializer

    def create(self, request, *args, **kwargs):
        response = super(RulebookList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Rulebook", "object": message}
        )
        return response


class RulebookDetail(RetrieveUpdateDestroyAPIView):

    queryset = Rulebook.objects.all()
    serializer_class = RulebookSerializer


class JobInstanceList(ListCreateAPIView):

    queryset = JobInstance.objects.all()
    serializer_class = JobInstanceSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobInstanceList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.JobInstance", "object": message}
        )
        return response


class JobInstanceDetail(RetrieveUpdateDestroyAPIView):

    queryset = JobInstance.objects.all()
    serializer_class = JobInstanceSerializer


class ActivationInstanceLogList(ListCreateAPIView):

    queryset = ActivationInstanceLog.objects.all()
    serializer_class = ActivationInstanceLogSerializer

    def create(self, request, *args, **kwargs):
        response = super(ActivationInstanceLogList, self).create(
            request, *args, **kwargs
        )
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.ActivationInstanceLog", "object": message}
        )
        return response


class ActivationInstanceLogDetail(RetrieveUpdateDestroyAPIView):

    queryset = ActivationInstanceLog.objects.all()
    serializer_class = ActivationInstanceLogSerializer


class RuleList(ListCreateAPIView):

    queryset = Rule.objects.all()
    serializer_class = RuleSerializer

    def create(self, request, *args, **kwargs):
        response = super(RuleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Rule", "object": message}
        )
        return response


class RuleDetail(RetrieveUpdateDestroyAPIView):

    queryset = Rule.objects.all()
    serializer_class = RuleSerializer


class RulesetList(ListCreateAPIView):

    queryset = Ruleset.objects.all()
    serializer_class = RulesetSerializer

    def create(self, request, *args, **kwargs):
        response = super(RulesetList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Ruleset", "object": message}
        )
        return response


class RulesetDetail(RetrieveUpdateDestroyAPIView):

    queryset = Ruleset.objects.all()
    serializer_class = RulesetSerializer


class JobList(ListCreateAPIView):

    queryset = Job.objects.all()
    serializer_class = JobSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Job", "object": message}
        )
        return response


class JobDetail(RetrieveUpdateDestroyAPIView):

    queryset = Job.objects.all()
    serializer_class = JobSerializer


class PlaybookList(ListCreateAPIView):

    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer

    def create(self, request, *args, **kwargs):
        response = super(PlaybookList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Playbook", "object": message}
        )
        return response


class PlaybookDetail(RetrieveUpdateDestroyAPIView):

    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer


class AuditRuleList(ListCreateAPIView):

    queryset = AuditRule.objects.all()
    serializer_class = AuditRuleSerializer

    def create(self, request, *args, **kwargs):
        response = super(AuditRuleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.AuditRule", "object": message}
        )
        return response


class AuditRuleDetail(RetrieveUpdateDestroyAPIView):

    queryset = AuditRule.objects.all()
    serializer_class = AuditRuleSerializer


class JobInstanceEventList(ListCreateAPIView):

    queryset = JobInstanceEvent.objects.all()
    serializer_class = JobInstanceEventSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobInstanceEventList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.JobInstanceEvent", "object": message}
        )
        return response


class JobInstanceEventDetail(RetrieveUpdateDestroyAPIView):

    queryset = JobInstanceEvent.objects.all()
    serializer_class = JobInstanceEventSerializer


class JobInstanceHostList(ListCreateAPIView):

    queryset = JobInstanceHost.objects.all()
    serializer_class = JobInstanceHostSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobInstanceHostList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.JobInstanceHost", "object": message}
        )
        return response


class JobInstanceHostDetail(RetrieveUpdateDestroyAPIView):

    queryset = JobInstanceHost.objects.all()
    serializer_class = JobInstanceHostSerializer


class ActivationList(ListCreateAPIView):

    queryset = Activation.objects.all()
    serializer_class = ActivationSerializer

    def create(self, request, *args, **kwargs):
        response = super(ActivationList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Activation", "object": message}
        )
        return response


class ActivationDetail(RetrieveUpdateDestroyAPIView):

    queryset = Activation.objects.all()
    serializer_class = ActivationSerializer


class RoleList(ListCreateAPIView):

    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    def create(self, request, *args, **kwargs):
        response = super(RoleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.Role", "object": message}
        )
        return response


class RoleDetail(RetrieveUpdateDestroyAPIView):

    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class RolePermissionList(ListCreateAPIView):

    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer

    def create(self, request, *args, **kwargs):
        response = super(RolePermissionList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.RolePermission", "object": message}
        )
        return response


class RolePermissionDetail(RetrieveUpdateDestroyAPIView):

    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer


class UserRoleList(ListCreateAPIView):

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer

    def create(self, request, *args, **kwargs):
        response = super(UserRoleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.UserRole", "object": message}
        )
        return response


class UserRoleDetail(RetrieveUpdateDestroyAPIView):

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer


class UserList(ListCreateAPIView):

    queryset = User.objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        response = super(UserList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["id"] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)(
            "eda_api", {"type": "create.User", "object": message}
        )
        return response


class UserDetail(RetrieveUpdateDestroyAPIView):

    queryset = User.objects.all()
    serializer_class = UserSerializer
