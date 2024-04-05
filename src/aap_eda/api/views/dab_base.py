from rest_framework.views import APIView

# from .mixins import CreateModelMixin, PartialUpdateOnlyModelMixin

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
        # raise Exception
        serializer_cls = super().get_serializer_class()
        if self.action == "create":
            return convert_to_create_serializer(serializer_cls)
        return serializer_cls

    def get_serializer(self, *args, **kwargs):
        if "context" in kwargs and hasattr(super(), 'get_serializer'):
            return super().get_serializer(*args, **kwargs)
        # raise Exception
        # print(f'serializer details in base view: {args}-{kwargs}')
        serializer_class = super().get_serializer_class()
        kwargs.setdefault('context', self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    # def get_response_serializer_class(self):
    #     return self.serializer
