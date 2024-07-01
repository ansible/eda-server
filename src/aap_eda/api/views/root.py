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


import logging

from django.conf import settings
from django.urls import URLPattern, URLResolver
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

LOGGER = logging.getLogger(__name__)


class ApiV1RootView(APIView):
    def get(self, request, *args, **kwargs):
        urls = get_api_v1_urls(request=request)
        return Response(urls)


def get_api_v1_urls(request=None):
    from aap_eda.api import urls

    def list_urls(urls):
        url_list = {}
        for url in urls:
            if isinstance(url, URLResolver):
                url_list.update(list_urls(url.url_patterns))
            elif isinstance(url, URLPattern):
                name = url.name
                if not name:
                    LOGGER.warning(
                        "URL %s has no name, DRF browsable API will omit it",
                        url.pattern,
                    )
                    continue
                if url.pattern.regex.groups:
                    continue
                url_list[name] = reverse(name, request=request)
        return url_list

    if settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT:
        urls = urls.v1_urls
    else:
        urls = urls.eda_v1_urls

    return list_urls(urls)
