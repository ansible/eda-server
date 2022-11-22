import json

from rest_framework.generics import ListCreateAPIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from {{app}}.models import ({%for model in models%}{%if model.api%}{{model.name}},
                            {%endif%}{%endfor%})
from {{app}}.serializers import ({%for model in models%}{%if model.api%}{{model.name}}Serializer,
                                        {%endif%}{%endfor%})

{%for model in models%}{%if model.api%}


class {{model.name}}List(ListCreateAPIView):

    queryset = {{model.name}}.objects.all()
    serializer_class = {{model.name}}Serializer

class {{model.name}}Detail(RetrieveUpdateDestroyAPIView):

    queryset = {{model.name}}.objects.all()
    serializer_class = {{model.name}}Serializer

{%endif%}{%endfor%}
