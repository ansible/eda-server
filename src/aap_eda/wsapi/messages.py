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

from typing import Optional

from pydantic import BaseModel


class Message(BaseModel):
    type: str


class EndOfResponse(BaseModel):
    type: str = "EndOfResponse"


class ActionMessage(Message):
    action: str
    action_uuid: str
    activation_id: int
    run_at: str
    ruleset: str
    ruleset_uuid: str
    rule: str
    rule_uuid: str
    matching_events: dict = {}
    status: Optional[str] = ""
    url: Optional[str] = ""
    rule_run_at: Optional[str] = ""
    playbook_name: Optional[str]
    job_template_name: Optional[str]
    organization: Optional[str]
    job_id: Optional[str]
    rc: Optional[int]
    delay: Optional[float]
    message: Optional[str]
    kind: Optional[str]
    controller_job_id: Optional[str]


class AnsibleEventMessage(Message):
    event: dict = {}
    run_at: str = None


class JobMessage(Message):
    job_id: str
    ansible_rulebook_id: int
    name: str
    ruleset: str
    rule: str
    hosts: str
    action: str


class WorkerMessage(Message):
    activation_id: int


class Rulebook(BaseModel):
    data: str
    type: str = "Rulebook"


class ExtraVars(BaseModel):
    data: str
    type: str = "ExtraVars"


# ssl_verify is either yes|no, future may have cert
class ControllerInfo(BaseModel):
    type: str = "ControllerInfo"
    url: str
    ssl_verify: str
    token: str = ""
    username: str = ""
    password: str = ""


class VaultPassword(BaseModel):
    type: str = "VaultPassword"
    label: Optional[str]
    password: str


class VaultCollection(BaseModel):
    type: str = "VaultCollection"
    data: list[VaultPassword]


class HeartbeatMessage(BaseModel):
    type: str = "SessionStats"
    activation_id: int
    stats: dict = {}
    reported_at: str
