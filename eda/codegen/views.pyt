import channels.layers
from asgiref.sync import async_to_sync

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

    def create(self, request, *args, **kwargs):
        response = super({{model.name}}List, self).create(request, *args, **kwargs)
        pk = response.data['{%for field in model.fields%}{%if field.pk%}{{field.name}}{%endif%}{%endfor%}']
        message = dict()
        {%if model.create_transform%}
        message.update(transform_dict({ {% for key, value in model.create_transform.iteritems()%} '{{key}}':'{{value}}',
                                       {%endfor%} },{{model.name}}.objects.filter(pk=pk).values(*[{% for key in model.create_transform.keys()%}'{{key}}',
                                                                                                  {%endfor%}])[0]))
        {%else%}
        message.update(response.data)
        {%endif%}
        message['{%for field in model.fields%}{%if field.pk%}{{field.name}}{%endif%}{%endfor%}'] = pk
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.send)('eda_api', {'type': 'create.{{model.name}}', "object": message})
        return response

class {{model.name}}Detail(RetrieveUpdateDestroyAPIView):

    queryset = {{model.name}}.objects.all()
    serializer_class = {{model.name}}Serializer

{%endif%}{%endfor%}
