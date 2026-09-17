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

import hmac


def timing_safe_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time using hmac.compare_digest.

    Python's hmac.compare_digest raises TypeError when either str
    operand contains non-ASCII characters — not just on a str-vs-bytes
    mismatch. Since Django provides HTTP header values as str with no
    ASCII guarantee, callers comparing credentials from headers must
    encode to bytes first. This function handles that conversion so
    callers don't need to remember the footgun.
    """
    return hmac.compare_digest(a.encode(), b.encode())
