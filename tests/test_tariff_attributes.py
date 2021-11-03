"""Tests for aiopvpc."""
from datetime import datetime, timedelta

import holidays
import pytest

from aiopvpc.const import REFERENCE_TZ
from aiopvpc.pvpc_data import _tariff_period_key

_HOLIDAYS_VERSION = tuple(map(int, holidays.__version__.split(".")))


@pytest.mark.parametrize(
    "year, days_weekend_p3, extra_days_p3",
    (
        (2021, 104, 7),
        (2022, 105, 7),
        (2023, 105, 9),
    ),
)
def test_number_of_national_holidays(year, days_weekend_p3, extra_days_p3):
    """Calculate days with full P3 valley period."""
    holidays_p3 = weekend_days_p3 = 0
    day = datetime(year, 1, 1, 15, tzinfo=REFERENCE_TZ)
    while day.year == year:
        if _tariff_period_key(day, False) == "P3":
            if day.isoweekday() > 5:
                weekend_days_p3 += 1
            else:
                holidays_p3 += 1
        day += timedelta(days=1)
    assert weekend_days_p3 == days_weekend_p3
    assert holidays_p3 == extra_days_p3
