"""Tests for aiopvpc."""

from datetime import datetime, timedelta

import pytest

from aiopvpc.const import REFERENCE_TZ
from aiopvpc.pvpc_tariff import get_current_and_next_tariff_periods


@pytest.mark.parametrize(
    "year, days_weekend_p3, extra_days_p3",
    (
        (2021, 104, 7),
        (2022, 105, 7),
        (2023, 105, 9),
        (2024, 104, 7),
        (2025, 104, 7),
    ),
)
def test_number_of_national_holidays(year, days_weekend_p3, extra_days_p3):
    """Calculate days with full P3 valley period."""
    holidays_p3 = weekend_days_p3 = 0
    day = datetime(year, 1, 1, 15, tzinfo=REFERENCE_TZ)
    while day.year == year:
        period, _, _ = get_current_and_next_tariff_periods(day, False)
        if period == "P3":
            if day.isoweekday() > 5:
                weekend_days_p3 += 1
            else:
                holidays_p3 += 1
        day += timedelta(days=1)
    assert weekend_days_p3 == days_weekend_p3
    assert holidays_p3 == extra_days_p3


@pytest.mark.parametrize("hour", range(24))
def test_may_day_is_p3_all_day(hour):
    """May 1 is a national holiday and must use valley period all day."""
    day = datetime(2026, 5, 1, hour, tzinfo=REFERENCE_TZ)

    period, _, _ = get_current_and_next_tariff_periods(day, False)

    assert period == "P3"
