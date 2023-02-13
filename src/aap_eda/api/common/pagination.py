#  Copyright 2023 Red Hat, Inc.
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

from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param

logger = logging.getLogger()


class StandardPagination(pagination.PageNumberPagination):
    def get_count(self, queryset):
        try:
            return queryset.count()
        except (AttributeError, TypeError):
            return len(queryset)

    def get_next_link(self):
        if not self.page.has_next():
            return None

        url = self.request and self.request.get_full_path() or ""
        url = url.encode("utf-8")

        page = self.page.number + self.page_size
        return replace_query_param(url, self.page_query_param, page)

    def get_previous_link(self):
        if not self.page.has_previous():
            return None

        url = self.request and self.request.get_full_path() or ""
        url = url.encode("utf-8")

        page = self.page.number - self.page_size
        if page <= 0:
            return remove_query_param(url, self.page_query_param)
        return replace_query_param(url, self.page_query_param, page)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.get_count(data),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page_size": self.page_size,
                "page_number": self.page.number,
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "example": 123,
                },
                "next": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "example": "/eda/api/v1/example/?{offset_param}=50&{limit_param}=100".format(  # noqa
                        offset_param=self.page_query_param,
                        limit_param=self.page_size_query_param,
                    ),
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "example": "/eda/api/v1/example/?{offset_param}=50&{limit_param}=100".format(  # noqa
                        offset_param=self.page_query_param,
                        limit_param=self.page_size_query_param,
                    ),
                },
                "page_size": {
                    "type": "integer",
                    "nullable": True,
                    "example": self.page_size_query_param,
                },
                "page_number": {
                    "type": "integer",
                    "nullable": True,
                    "example": self.page_query_param,
                },
                "results": schema,
            },
        }
