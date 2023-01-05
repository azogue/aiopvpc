"""Tests for aiopvpc."""
from datetime import datetime, timedelta

import holidays
import pytest

from aiopvpc.const import REFERENCE_TZ
from aiopvpc.pvpc_tariff import get_current_and_next_tariff_periods

_HOLIDAYS_VERSION = tuple(map(int, holidays.__version__.split(".")))


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
