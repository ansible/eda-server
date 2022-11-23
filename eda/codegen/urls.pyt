from django.urls import include, path
{%for model in models-%}{%if model.api%}
from eda.api_views import ({{model.name}}List, {{model.name}}Detail)
{%-endif%}
{%-endfor%}


urlpatterns = [];
{%for model in models%}{%if model.api%}

urlpatterns += [
    path('{{model.name.lower()}}/', {{model.name}}List.as_view(), name='eda_{{model.name.lower()}}_list'),
    path('{{model.name.lower()}}/<int:pk>/', {{model.name}}Detail.as_view(), name='eda_{{model.name.lower()}}_detail'),
];
{%-endif%}
{%-endfor%}

__all__ = ['urlpatterns']
