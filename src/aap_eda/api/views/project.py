from rest_framework import mixins, viewsets

from aap_eda.api import serializers
from aap_eda.core import models


class ExtraVarViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.ExtraVar.objects.all()
    serializer_class = serializers.ExtraVarSerializer


class PlaybookViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = models.Playbook.objects.all()
    serializer_class = serializers.PlaybookSerializer
