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

from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param


class StandardPagination(pagination.PageNumberPagination):
    page_size_query_param = "page_size"

    def get_next_link(self):
        if not self.page.has_next():
            return None

        url = ""
        if self.request:
            url = self.request.get_full_path()

        return replace_query_param(
            url, self.page_query_param, self.page.next_page_number()
        )

    def get_previous_link(self):
        if not self.page.has_previous():
            return None

        url = ""
        if self.request:
            url = self.request.get_full_path()

        previous_page = self.page.previous_page_number()
        if previous_page <= 0:
            return remove_query_param(url, self.page_query_param)
        return replace_query_param(url, self.page_query_param, previous_page)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page_size": self.get_page_size(self.request),
                "page": self.page.number,
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        next_page_url = (
            f"/eda/api/v1/example/"
            f"?{self.page_query_param}=51&{self.page_size_query_param}=100"
        )
        prev_page_url = (
            f"/eda/api/v1/example/"
            f"?{self.page_query_param}=49&{self.page_size_query_param}=100"
        )
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
                    "example": next_page_url,
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "example": prev_page_url,
                },
                "page_size": {
                    "type": "integer",
                    "nullable": True,
                    "example": 100,
                },
                "page": {
                    "type": "integer",
                    "nullable": True,
                    "example": 50,
                },
                "results": schema,
            },
        }
