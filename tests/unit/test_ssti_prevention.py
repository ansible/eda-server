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

"""Regression tests for SSTI prevention (AAP-76179 / CTRL-001)."""

import pytest
from jinja2.exceptions import SecurityError

from aap_eda.core.utils.credentials import (
    InjectorInvalidTemplateKey,
    _check_jinja_string,
)
from aap_eda.core.utils.strings import _render_string, substitute_variables
from aap_eda.services.activation import exceptions as activation_exceptions
from aap_eda.services.activation.engine.ports import (
    find_ports,
    render_string as ports_render_string,
)

SSTI_PAYLOAD = "{{ ''.__class__.__mro__ }}"


class TestSandboxEnforcement:
    """Each rendering call site rejects SSTI payloads."""

    def test_strings_render_blocks_ssti(self):
        with pytest.raises(ValueError, match="unsafe operations"):
            _render_string(SSTI_PAYLOAD, {})

    def test_credentials_check_blocks_ssti(self):
        with pytest.raises(InjectorInvalidTemplateKey):
            _check_jinja_string(SSTI_PAYLOAD, {})

    def test_ports_render_blocks_ssti(self):
        with pytest.raises(SecurityError):
            ports_render_string(SSTI_PAYLOAD, {})

    def test_ports_find_ports_wraps_ssti(self):
        rulebook = """
---
- name: test
  hosts: all
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: "{{ ''.__class__.__mro__ }}"
"""
        with pytest.raises(activation_exceptions.ActivationStartError):
            find_ports(rulebook, {})


class TestLegitimateTemplates:
    """Sandboxing does not break normal template rendering."""

    def test_render_string(self):
        result = _render_string("{{ name }}", {"name": "hello"})
        assert result == "hello"
        assert isinstance(result, str)

    def test_render_string_passthrough(self):
        assert _render_string("plain text", {}) == "plain text"

    def test_substitute_variables_dict(self):
        result = substitute_variables(
            {"a": "{{ x }}", "b": "literal"}, {"x": "resolved"}
        )
        assert result == {"a": "resolved", "b": "literal"}

    def test_ports_render(self):
        assert ports_render_string("{{ port }}", {"port": 8080}) == 8080


class TestNativeTypePreservation:
    """Sandboxed environment preserves native Python types."""

    def test_integer_preserved(self):
        result = _render_string("{{ value }}", {"value": 42})
        assert result == 42
        assert isinstance(result, int)

    def test_boolean_preserved(self):
        result = _render_string("{{ flag }}", {"flag": True})
        assert result is True
        assert isinstance(result, bool)

    def test_float_preserved(self):
        result = _render_string("{{ value }}", {"value": 3.14})
        assert result == 3.14
        assert isinstance(result, float)

    def test_list_preserved(self):
        result = _render_string("{{ items }}", {"items": [1, 2, 3]})
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_dict_access_preserves_type(self):
        result = _render_string(
            "{{ config.port }}", {"config": {"port": 8080}}
        )
        assert result == 8080
        assert isinstance(result, int)

    def test_arithmetic_preserves_type(self):
        result = _render_string("{{ x + y }}", {"x": 10, "y": 20})
        assert result == 30
        assert isinstance(result, int)

    def test_ports_render_returns_int(self):
        result = ports_render_string("{{ port }}", {"port": 5000})
        assert result == 5000
        assert isinstance(result, int)
