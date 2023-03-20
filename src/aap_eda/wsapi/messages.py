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

from pydantic import BaseModel


class Message(BaseModel):
    type: str


class ActionMessage(Message):
    action: str
    activation_id: int
    playbook_name: str = ""
    job_id: str
    ruleset: str
    rule: str
    rc: int = 0
    status: str
    run_at: str = None
    matching_events: dict = {}


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


class Inventory(BaseModel):
    data: str
    type: str = "Inventory"


class ExtraVars(BaseModel):
    data: str
    type: str = "ExtraVars"


class Hello(BaseModel):
    data: str = {}
    type: str = "Hello"
