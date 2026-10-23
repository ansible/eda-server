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

from datetime import datetime, timezone as datetime_timezone

import isodate


def retention_cutoff(
    duration: str, *, now: datetime | None = None
) -> datetime:
    """Return the UTC cutoff for a positive ISO 8601 duration.

    Calendar months and years use ``isodate.Duration`` subtraction semantics:
    the month is shifted and the day is clamped to that month's last day.
    Other duration components are subtracted as elapsed time.
    """
    now = now or datetime.now(datetime_timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("The current time must be timezone-aware.")
    now = now.astimezone(datetime_timezone.utc)

    try:
        parsed = isodate.parse_duration(duration)
        cutoff = now - parsed
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "retention_duration must be a valid ISO 8601 duration."
        ) from exc

    if cutoff >= now:
        raise ValueError("retention_duration must produce a past cutoff.")
    return cutoff
