import json
import channels
from utils import transform_dict

from awx.api.generics import ListCreateAPIView
from awx.api.generics import RetrieveUpdateDestroyAPIView
from .models import (
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
from .v2_api_serializers import (
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

    def create(self, request, *args, **kwargs):
        response = super(ActivationInstanceJobInstanceList, self).create(
            request, *args, **kwargs
        )
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "ActivationInstanceJobInstanceCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class ActivationInstanceJobInstanceDetail(RetrieveUpdateDestroyAPIView):

    model = ActivationInstanceJobInstance
    serializer_class = ActivationInstanceJobInstanceSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "ActivationInstanceJobInstanceUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(ActivationInstanceJobInstanceDetail, self).update(
            request, pk, *args, **kwargs
        )

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(ActivationInstanceJobInstanceDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(ActivationInstanceJobInstanceDetail, self).destroy(
            request, pk, *args, **kwargs
        )


class ActivationInstanceList(ListCreateAPIView):

    model = ActivationInstance
    serializer_class = ActivationInstanceSerializer

    def create(self, request, *args, **kwargs):
        response = super(ActivationInstanceList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "ActivationInstanceCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class ActivationInstanceDetail(RetrieveUpdateDestroyAPIView):

    model = ActivationInstance
    serializer_class = ActivationInstanceSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "ActivationInstanceUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(ActivationInstanceDetail, self).update(
            request, pk, *args, **kwargs
        )

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(ActivationInstanceDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(ActivationInstanceDetail, self).destroy(
            request, pk, *args, **kwargs
        )


class ExtraVarList(ListCreateAPIView):

    model = ExtraVar
    serializer_class = ExtraVarSerializer

    def create(self, request, *args, **kwargs):
        response = super(ExtraVarList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "ExtraVarCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class ExtraVarDetail(RetrieveUpdateDestroyAPIView):

    model = ExtraVar
    serializer_class = ExtraVarSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "ExtraVarUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(ExtraVarDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(ExtraVarDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(ExtraVarDetail, self).destroy(request, pk, *args, **kwargs)


class ProjectList(ListCreateAPIView):

    model = Project
    serializer_class = ProjectSerializer

    def create(self, request, *args, **kwargs):
        response = super(ProjectList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "ProjectCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class ProjectDetail(RetrieveUpdateDestroyAPIView):

    model = Project
    serializer_class = ProjectSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "ProjectUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(ProjectDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(ProjectDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(ProjectDetail, self).destroy(request, pk, *args, **kwargs)


class InventoryList(ListCreateAPIView):

    model = Inventory
    serializer_class = InventorySerializer

    def create(self, request, *args, **kwargs):
        response = super(InventoryList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "InventoryCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class InventoryDetail(RetrieveUpdateDestroyAPIView):

    model = Inventory
    serializer_class = InventorySerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "InventoryUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(InventoryDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(InventoryDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(InventoryDetail, self).destroy(request, pk, *args, **kwargs)


class RulebookList(ListCreateAPIView):

    model = Rulebook
    serializer_class = RulebookSerializer

    def create(self, request, *args, **kwargs):
        response = super(RulebookList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "RulebookCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class RulebookDetail(RetrieveUpdateDestroyAPIView):

    model = Rulebook
    serializer_class = RulebookSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "RulebookUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(RulebookDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(RulebookDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(RulebookDetail, self).destroy(request, pk, *args, **kwargs)


class JobInstanceList(ListCreateAPIView):

    model = JobInstance
    serializer_class = JobInstanceSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobInstanceList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "JobInstanceCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class JobInstanceDetail(RetrieveUpdateDestroyAPIView):

    model = JobInstance
    serializer_class = JobInstanceSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "JobInstanceUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(JobInstanceDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(JobInstanceDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(JobInstanceDetail, self).destroy(request, pk, *args, **kwargs)


class ActivationInstanceLogList(ListCreateAPIView):

    model = ActivationInstanceLog
    serializer_class = ActivationInstanceLogSerializer

    def create(self, request, *args, **kwargs):
        response = super(ActivationInstanceLogList, self).create(
            request, *args, **kwargs
        )
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "ActivationInstanceLogCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class ActivationInstanceLogDetail(RetrieveUpdateDestroyAPIView):

    model = ActivationInstanceLog
    serializer_class = ActivationInstanceLogSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "ActivationInstanceLogUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(ActivationInstanceLogDetail, self).update(
            request, pk, *args, **kwargs
        )

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(ActivationInstanceLogDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(ActivationInstanceLogDetail, self).destroy(
            request, pk, *args, **kwargs
        )


class RuleList(ListCreateAPIView):

    model = Rule
    serializer_class = RuleSerializer

    def create(self, request, *args, **kwargs):
        response = super(RuleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "RuleCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class RuleDetail(RetrieveUpdateDestroyAPIView):

    model = Rule
    serializer_class = RuleSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "RuleUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(RuleDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(RuleDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(RuleDetail, self).destroy(request, pk, *args, **kwargs)


class RulesetList(ListCreateAPIView):

    model = Ruleset
    serializer_class = RulesetSerializer

    def create(self, request, *args, **kwargs):
        response = super(RulesetList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "RulesetCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class RulesetDetail(RetrieveUpdateDestroyAPIView):

    model = Ruleset
    serializer_class = RulesetSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "RulesetUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(RulesetDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(RulesetDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(RulesetDetail, self).destroy(request, pk, *args, **kwargs)


class JobList(ListCreateAPIView):

    model = Job
    serializer_class = JobSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "JobCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class JobDetail(RetrieveUpdateDestroyAPIView):

    model = Job
    serializer_class = JobSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "JobUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(JobDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(JobDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(JobDetail, self).destroy(request, pk, *args, **kwargs)


class PlaybookList(ListCreateAPIView):

    model = Playbook
    serializer_class = PlaybookSerializer

    def create(self, request, *args, **kwargs):
        response = super(PlaybookList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "PlaybookCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class PlaybookDetail(RetrieveUpdateDestroyAPIView):

    model = Playbook
    serializer_class = PlaybookSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "PlaybookUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(PlaybookDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(PlaybookDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(PlaybookDetail, self).destroy(request, pk, *args, **kwargs)


class AuditRuleList(ListCreateAPIView):

    model = AuditRule
    serializer_class = AuditRuleSerializer

    def create(self, request, *args, **kwargs):
        response = super(AuditRuleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "AuditRuleCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class AuditRuleDetail(RetrieveUpdateDestroyAPIView):

    model = AuditRule
    serializer_class = AuditRuleSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "AuditRuleUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(AuditRuleDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(AuditRuleDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(AuditRuleDetail, self).destroy(request, pk, *args, **kwargs)


class JobInstanceEventList(ListCreateAPIView):

    model = JobInstanceEvent
    serializer_class = JobInstanceEventSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobInstanceEventList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "JobInstanceEventCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class JobInstanceEventDetail(RetrieveUpdateDestroyAPIView):

    model = JobInstanceEvent
    serializer_class = JobInstanceEventSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "JobInstanceEventUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(JobInstanceEventDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(JobInstanceEventDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(JobInstanceEventDetail, self).destroy(request, pk, *args, **kwargs)


class JobInstanceHostList(ListCreateAPIView):

    model = JobInstanceHost
    serializer_class = JobInstanceHostSerializer

    def create(self, request, *args, **kwargs):
        response = super(JobInstanceHostList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "JobInstanceHostCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class JobInstanceHostDetail(RetrieveUpdateDestroyAPIView):

    model = JobInstanceHost
    serializer_class = JobInstanceHostSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "JobInstanceHostUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(JobInstanceHostDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(JobInstanceHostDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(JobInstanceHostDetail, self).destroy(request, pk, *args, **kwargs)


class ActivationList(ListCreateAPIView):

    model = Activation
    serializer_class = ActivationSerializer

    def create(self, request, *args, **kwargs):
        response = super(ActivationList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "ActivationCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class ActivationDetail(RetrieveUpdateDestroyAPIView):

    model = Activation
    serializer_class = ActivationSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "ActivationUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(ActivationDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(ActivationDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(ActivationDetail, self).destroy(request, pk, *args, **kwargs)


class RoleList(ListCreateAPIView):

    model = Role
    serializer_class = RoleSerializer

    def create(self, request, *args, **kwargs):
        response = super(RoleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "RoleCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class RoleDetail(RetrieveUpdateDestroyAPIView):

    model = Role
    serializer_class = RoleSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "RoleUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(RoleDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(RoleDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(RoleDetail, self).destroy(request, pk, *args, **kwargs)


class RolePermissionList(ListCreateAPIView):

    model = RolePermission
    serializer_class = RolePermissionSerializer

    def create(self, request, *args, **kwargs):
        response = super(RolePermissionList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "RolePermissionCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class RolePermissionDetail(RetrieveUpdateDestroyAPIView):

    model = RolePermission
    serializer_class = RolePermissionSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "RolePermissionUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(RolePermissionDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(RolePermissionDetail, self).partial_update(
            request, pk, *args, **kwargs
        )

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(RolePermissionDetail, self).destroy(request, pk, *args, **kwargs)


class UserRoleList(ListCreateAPIView):

    model = UserRole
    serializer_class = UserRoleSerializer

    def create(self, request, *args, **kwargs):
        response = super(UserRoleList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "UserRoleCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class UserRoleDetail(RetrieveUpdateDestroyAPIView):

    model = UserRole
    serializer_class = UserRoleSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "UserRoleUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(UserRoleDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(UserRoleDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(UserRoleDetail, self).destroy(request, pk, *args, **kwargs)


class UserList(ListCreateAPIView):

    model = User
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        response = super(UserList, self).create(request, *args, **kwargs)
        pk = response.data["id"]
        message = dict()

        message.update(response.data)

        message["msg_type"] = "UserCreate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )
        return response


class UserDetail(RetrieveUpdateDestroyAPIView):

    model = User
    serializer_class = UserSerializer

    def update(self, request, pk=None, *args, **kwargs):
        message = dict()
        message.update(json.loads(request.body))
        message["msg_type"] = "UserUpdate"
        message["id"] = pk
        message["sender"] = 0

        for topology_id in Topology.objects.all().values_list("topology_id", flat=True):

            channels.Group("topology-%s" % topology_id).send(
                {"text": json.dumps([message["msg_type"], message])}
            )

        return super(UserDetail, self).update(request, pk, *args, **kwargs)

    def partial_update(self, request, pk=None, *args, **kwargs):
        return super(UserDetail, self).partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        return super(UserDetail, self).destroy(request, pk, *args, **kwargs)
