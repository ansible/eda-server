import json
import channels
from utils import transform_dict

from rest_framework.generics import ListCreateAPIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from {{app}}.models import ({%for model in models%}{%if model.api%}{{model.name}},
                            {%endif%}{%endfor%})
from {{app}}.v2_api_serializers import ({%for model in models%}{%if model.api%}{{model.name}}Serializer,
                                        {%endif%}{%endfor%})

{%for model in models%}{%if model.api%}


class {{model.name}}List(ListCreateAPIView):

    model = {{model.name}}
    serializer_class = {{model.name}}Serializer

class {{model.name}}Detail(RetrieveUpdateDestroyAPIView):

    model = {{model.name}}
    serializer_class = {{model.name}}Serializer

{%endif%}{%endfor%}
