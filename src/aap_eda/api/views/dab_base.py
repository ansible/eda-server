#  Copyright 2024 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from rest_framework.serializers import Serializer
from rest_framework.views import APIView

registry = {}


def convert_to_create_serializer(cls):
    """Given a DRF serializer class, return read-only version.

    This is done for
    https://github.com/OpenAPITools/openapi-generator
    For fields required in responses, but not used in requests,
    OpenAPI readOnly is insufficient
    https://github.com/OpenAPITools/openapi-generator/issues/14280
    #issuecomment-1435960939
    """
    global registry

    create_serializer_name = (
        cls.__name__.replace("Serializer", "") + "CreateSerializer"
    )
    if create_serializer_name in registry:
        return registry[create_serializer_name]

    create_field_list = []
    for field_name, field in cls().fields.items():
        if not field.read_only:
            create_field_list.append(field_name)

    class Meta(cls.Meta):
        fields = create_field_list

    create_cls = type(create_serializer_name, (cls,), {"Meta": Meta})
    registry[create_serializer_name] = create_cls

    return create_cls


class BaseAPIView(APIView):
    def get_serializer_class(self):
        if not hasattr(super(), "get_serializer_class"):
            # Use base serializer for DAB views that do not give any serializer
            return Serializer
        serializer_cls = super().get_serializer_class()
        if self.action == "create":
            return convert_to_create_serializer(serializer_cls)
        return serializer_cls

    def get_serializer(self, *args, **kwargs):
        # We use the presence of context here to know we are called
        # by drf_spectacular for schema generation
        # in these cases we use a custom creation serializer
        if "context" in kwargs and hasattr(super(), "get_serializer"):
            return super().get_serializer(*args, **kwargs)
        elif not hasattr(super(), "get_serializer_class"):
            return None

        # If not, we are processing a real request
        # in that case, we do not want the phony and incorrect serializer
        # to do that, we duplicate the DRF version of get_serializer
        serializer_class = super().get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)
