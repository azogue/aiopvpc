"""Tests for aiopvpc."""

from datetime import date, datetime, timedelta

import pytest

from aiopvpc.const import REFERENCE_TZ
from aiopvpc.pvpc_tariff import (
    get_current_and_next_tariff_periods,
    is_national_p3_holiday,
)


@pytest.mark.parametrize(
    "year, days_weekend_p3, extra_days_p3",
    (
        (2021, 104, 6),
        (2022, 105, 6),
        (2023, 105, 8),
        (2024, 104, 6),
        (2025, 104, 6),
        (2026, 104, 6),
        (2027, 104, 6),
        (2028, 106, 8),
        (2029, 104, 7),
        (2030, 104, 6),
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


@pytest.mark.parametrize(
    "day, expected_holiday, expected_period_11h",
    (
        (date(2024, 3, 29), False, "P1"),  # Good Friday (movable -> weekday)
        (date(2025, 4, 18), False, "P1"),  # Good Friday (movable -> weekday)
        (date(2026, 4, 3), False, "P1"),  # Good Friday (movable -> weekday)
        (date(2026, 1, 1), True, "P3"),  # Año Nuevo
        (date(2026, 1, 6), True, "P3"),  # Epifanía del Señor
        (date(2026, 5, 1), True, "P3"),  # Fiesta del Trabajo
        (date(2026, 10, 12), True, "P3"),  # Fiesta Nacional
        (date(2026, 12, 8), True, "P3"),  # Inmaculada Concepción
        (date(2026, 12, 25), True, "P3"),  # Navidad
    ),
)
def test_cnmc_fixed_holidays_and_good_friday(
    day: date, expected_holiday: bool, expected_period_11h: str
):
    """Verify CNMC Circular 3/2020 Art. 7.3 P3 holiday rules."""
    assert is_national_p3_holiday(day) is expected_holiday
    ts = datetime(day.year, day.month, day.day, 11, tzinfo=REFERENCE_TZ)
    period, _, _ = get_current_and_next_tariff_periods(ts, False)
    assert period == expected_period_11h


@pytest.mark.parametrize(
    "zone_ceuta_melilla, expected_p1, expected_p2",
    (
        (False, {10, 11, 12, 13, 18, 19, 20, 21}, {8, 9, 14, 15, 16, 17, 22, 23}),
        (True, {11, 12, 13, 14, 19, 20, 21, 22}, {8, 9, 10, 15, 16, 17, 18, 23}),
    ),
)
def test_weekday_hourly_tariff_periods(
    zone_ceuta_melilla: bool, expected_p1: set[int], expected_p2: set[int]
):
    """Verify P1/P2/P3 hourly windows for Peninsula and Ceuta/Melilla."""
    # Wednesday 2026-11-18 (normal weekday)
    for hour in range(24):
        ts = datetime(2026, 11, 18, hour, tzinfo=REFERENCE_TZ)
        period, next_period, delta = get_current_and_next_tariff_periods(
            ts, zone_ceuta_melilla
        )
        if hour < 8:
            assert period == "P3"
        elif hour in expected_p2:
            assert period == "P2"
        else:
            assert hour in expected_p1
            assert period == "P1"
        assert next_period != period
        assert delta >= timedelta(hours=1)
