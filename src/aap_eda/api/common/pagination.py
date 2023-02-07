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


class StandardPagination(pagination.LimitOffsetPagination):
    def get_next_link(self):
        if self.offset + self.limit >= self.count:
            return None

        url = self.request and self.request.get_full_path() or ""
        url = url.encode("utf-8")

        offset = self.offset + self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_previous_link(self):
        if self.offset <= 0:
            return None

        url = self.request and self.request.get_full_path() or ""
        url = url.encode("utf-8")

        offset = self.offset - self.limit
        if offset <= 0:
            return remove_query_param(url, self.offset_query_param)
        return replace_query_param(url, self.offset_query_param, offset)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "limit": self.limit,
                "offset": self.offset,
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
                        offset_param=self.offset_query_param,
                        limit_param=self.limit_query_param,
                    ),
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "example": "/eda/api/v1/example/?{offset_param}=50&{limit_param}=100".format(  # noqa
                        offset_param=self.offset_query_param,
                        limit_param=self.limit_query_param,
                    ),
                },
                "limit": {
                    "type": "integer",
                    "nullable": True,
                    "example": self.limit_query_param,
                },
                "offset": {
                    "type": "integer",
                    "nullable": True,
                    "example": self.offset_query_param,
                },
                "results": schema,
            },
        }


class ListPagination(StandardPagination):
    def __init__(self, data, request):
        self.data = data
        self.count = len(self.data)
        self.request = request
        self.offset = self.get_offset(request)
        self.limit = self.get_limit(request)

    @property
    def paginate_data(self):
        max_index = min(self.limit, self.count)
        try:
            paginated_data = self.data[self.offset : self.offset + max_index]
        except IndexError:
            paginated_data = []
        return paginated_data
