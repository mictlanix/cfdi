"""The shared Mexico City time: the offset sealing and the simulated PAC's clock use."""

from datetime import UTC, datetime, timedelta

from mictlanix.cfdi import _mexico


def test_the_offset_is_a_fixed_utc_minus_6() -> None:
    assert _mexico.MEXICO_CITY.utcoffset(None) == timedelta(hours=-6)


def test_now_is_naive_mexico_city_time_without_microseconds() -> None:
    now = _mexico.now()
    expected = (datetime.now(UTC) - timedelta(hours=6)).replace(tzinfo=None)
    assert now.tzinfo is None
    assert now.microsecond == 0
    assert abs(now - expected) < timedelta(seconds=2)
