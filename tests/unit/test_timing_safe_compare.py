#  Copyright 2026 Red Hat, Inc.
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

from aap_eda.core.utils.crypto import timing_safe_compare


def test_equal_strings():
    assert timing_safe_compare("abc", "abc") is True


def test_unequal_strings():
    assert timing_safe_compare("abc", "xyz") is False


def test_empty_strings():
    assert timing_safe_compare("", "") is True


def test_empty_vs_nonempty():
    assert timing_safe_compare("", "a") is False


def test_non_ascii_equal():
    assert timing_safe_compare("café", "café") is True


def test_non_ascii_unequal():
    assert timing_safe_compare("café", "naïve") is False
