"""Tests for aiopvpc."""
from datetime import datetime, timedelta

import pytest

from aiopvpc.const import REFERENCE_TZ
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "ts, source, timezone, zone_cm, n_prices, n_calls, n_prices_8h, available_8h",
    (
        ("2021-10-30 00:00:00+08:00", "apidatos", TZ_TEST, False, 0, 1, 0, False),
        ("2021-10-30 00:00:00", "apidatos", TZ_TEST, False, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "apidatos", TZ_TEST, False, 25, 1, 25, True),
        # ("2022-03-27 20:00:00", "apidatos", TZ_TEST, False, 23, 2, 23, False),
        # ("2022-03-27 20:00:00+04:00", "apidatos", TZ_TEST, False, 23, 1, 23, False),
        ("2021-10-30 21:00:00", "apidatos", TZ_TEST, False, 49, 2, 26, True),
        ("2021-10-30 21:00:00+01:00", "apidatos", TZ_TEST, False, 49, 2, 26, True),
        ("2021-10-30 00:00:00", "apidatos", REFERENCE_TZ, True, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "apidatos", REFERENCE_TZ, True, 25, 1, 25, True),
        # ("2022-03-27 20:00:00", "apidatos", REFERENCE_TZ, True, 23, 2, 23, False),
        ("2021-10-30 21:00:00", "apidatos", REFERENCE_TZ, True, 49, 2, 25, True),
        ("2021-06-01 09:00:00", "apidatos", REFERENCE_TZ, True, 24, 1, 24, True),
        ("2021-06-01 09:00:00", "apidatos", TZ_TEST, True, 24, 1, 24, True),
        ("2021-10-30 00:00:00+08:00", "esios_public", TZ_TEST, False, 0, 1, 0, False),
        ("2021-10-30 00:00:00", "esios_public", TZ_TEST, False, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "esios_public", TZ_TEST, False, 25, 1, 25, True),
        ("2022-03-27 20:00:00", "esios_public", TZ_TEST, False, 23, 2, 23, False),
        ("2022-03-27 20:00:00+04:00", "esios_public", TZ_TEST, False, 23, 1, 23, False),
        ("2021-10-30 21:00:00", "esios_public", TZ_TEST, False, 49, 2, 26, True),
        ("2021-10-30 21:00:00+01:00", "esios_public", TZ_TEST, False, 49, 2, 26, True),
        ("2021-10-30 00:00:00", "esios_public", REFERENCE_TZ, True, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "esios_public", REFERENCE_TZ, True, 25, 1, 25, True),
        ("2022-03-27 20:00:00", "esios_public", REFERENCE_TZ, True, 23, 2, 23, False),
        ("2021-10-30 21:00:00", "esios_public", REFERENCE_TZ, True, 49, 2, 25, True),
        ("2021-06-01 09:00:00", "esios_public", REFERENCE_TZ, True, 24, 1, 24, True),
        ("2021-06-01 09:00:00", "esios_public", TZ_TEST, True, 24, 1, 24, True),
    ),
)
@pytest.mark.asyncio
async def test_price_extract(
    ts,
    source,
    timezone,
    zone_cm,
    n_prices,
    n_calls,
    n_prices_8h,
    available_8h,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(ts)
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        local_timezone=timezone,
        data_source=source,
    )

    pvpc_data.source_available = True
    assert not pvpc_data.process_state_and_attributes(day)
    assert mock_session.call_count == 0

    await pvpc_data.async_update_prices(day)
    pvpc_data.process_state_and_attributes(day)
    assert len(pvpc_data._current_prices) == n_prices
    assert mock_session.call_count == n_calls

    has_prices = pvpc_data.process_state_and_attributes(day + timedelta(hours=10))
    assert len(pvpc_data._current_prices) == n_prices_8h
    assert has_prices == available_8h
    if has_prices:
        last_dt, last_p = list(pvpc_data._current_prices.items())[-1]
        assert last_dt.astimezone(timezone).hour == 23
