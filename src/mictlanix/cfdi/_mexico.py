"""Mexico City time, the local time of the SAT's naive datetimes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Mexico City time, a fixed UTC-6 since Mexico abolished daylight saving time in October 2022,
# so for every certificate still valid. The SAT's naive datetimes, `Fecha` among them, are
# local time.
MEXICO_CITY = timezone(timedelta(hours=-6))


def now() -> datetime:
    """The current naive Mexico City time, without microseconds."""
    return datetime.now(MEXICO_CITY).replace(tzinfo=None, microsecond=0)
