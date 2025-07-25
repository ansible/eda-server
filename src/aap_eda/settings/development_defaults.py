#  Copyright 2025 Red Hat, Inc.
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
DEBUG = True
SECRET_KEY = "insecure"
DB_PASSWORD = "secret"
DB_HOST = "localhost"
MQ_HOST = "localhost"

ANSIBLE_BASE_MANAGED_ROLE_REGISTRY = {}
ANSIBLE_BASE_JWT_KEY = "https://localhost"
ANSIBLE_BASE_JWT_VALIDATE_CERT = False
ALLOW_LOCAL_RESOURCE_MANAGEMENT = True

RESOURCE_SERVER = {
    "URL": None,
    "SECRET_KEY": None,
    "VALIDATE_HTTPS": False,
}
