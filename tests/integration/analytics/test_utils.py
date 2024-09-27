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

import datetime
import json

from django.core.serializers.json import DjangoJSONEncoder

from aap_eda.analytics.utils import datetime_hook


def test_datetime_hook():
    data = {
        "started_at": "2024-09-13 14:42:49.188",
        "ended_at": "2024-09-13 14:43:10,654",
    }
    data_json = json.dumps(data, cls=DjangoJSONEncoder)

    result = json.loads(data_json, object_hook=datetime_hook)

    assert isinstance(result["started_at"], datetime.datetime) is True
    assert isinstance(result["ended_at"], datetime.datetime) is True


def test_bad_datetime_hook():
    data = {
        "started_at": "2024-09-13 14:42:49.188",
        "ended_at": "bad_2024-09-13 14:43:10,654",
    }
    data_json = json.dumps(data, cls=DjangoJSONEncoder)

    result = json.loads(data_json, object_hook=datetime_hook)

    assert isinstance(result["started_at"], datetime.datetime) is True
    assert isinstance(result["ended_at"], datetime.datetime) is False
