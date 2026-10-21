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

import importlib
import os

from django import conf

from aap_eda.settings import default


def test_eda_mode():
    # pytest defaults
    assert conf.settings.MODE == "development"
    dev_sec_key = conf.settings.SECRET_KEY
    sec_env_var = os.getenv("EDA_SECRET_KEY")

    # default to production mode (need to provide SECRET_KEY)
    os.environ.pop("EDA_MODE")
    os.environ["EDA_SECRET_KEY"] = "product"
    importlib.reload(default)
    importlib.reload(conf)
    assert conf.settings.MODE == "production"
    assert conf.settings.SECRET_KEY == "product"

    # roll back to pytest defaults
    os.environ["EDA_MODE"] = "development"
    if sec_env_var:
        os.environ["EDA_SECRET_KEY"] = sec_env_var
    else:
        os.environ.pop("EDA_SECRET_KEY")
    importlib.reload(default)
    importlib.reload(conf)
    assert conf.settings.MODE == "development"
    assert conf.settings.SECRET_KEY == dev_sec_key


def test_import_from_yaml():
    dev_sec_key = conf.settings.SECRET_KEY
    sec_env_var = os.getenv("EDA_SECRET_KEY")
    if sec_env_var:
        os.environ.pop("EDA_SECRET_KEY")

    file_path = os.path.abspath(__file__)
    file_dir = os.path.dirname(file_path)
    user_settings_file = os.path.join(file_dir, "data/demo_settings.yaml")
    os.environ["EDA_SETTINGS_FILE"] = user_settings_file
    importlib.reload(default)
    importlib.reload(conf)
    assert conf.settings.SECRET_KEY == "dev.key"

    # roll back
    os.environ.pop("EDA_SETTINGS_FILE", None)
    if sec_env_var:
        os.environ["EDA_SECRET_KEY"] = sec_env_var
    importlib.reload(default)
    importlib.reload(conf)
    assert conf.settings.SECRET_KEY == dev_sec_key
