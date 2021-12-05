"""Tests for aiopvpc."""
from datetime import datetime

import pytest

from aiopvpc.const import REFERENCE_TZ, TARIFFS, UTC_TZ
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "local_tz, source, tariff, expected_18h",
    (
        (TZ_TEST, "apidatos", TARIFFS[0], 0.23144),
        (REFERENCE_TZ, "apidatos", TARIFFS[0], 0.23144),
        (REFERENCE_TZ, "apidatos", TARIFFS[1], 0.13813),
        (TZ_TEST, "esios_public", TARIFFS[0], 0.23144),
        (REFERENCE_TZ, "esios_public", TARIFFS[0], 0.23144),
        (REFERENCE_TZ, "esios_public", TARIFFS[1], 0.13813),
    ),
)
@pytest.mark.asyncio
async def test_geo_ids(local_tz, source, tariff, expected_18h):
    """Test different prices for different geo zones."""
    start = datetime(2021, 6, 1, 10, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    pvpc_data = PVPCData(
        session=mock_session,
        tariff=tariff,
        local_timezone=local_tz,
        data_source=source,
    )
    await pvpc_data.async_update_prices(start)
    assert pvpc_data.process_state_and_attributes(start)
    # for ts, price in pvpc_data._current_prices.items():
    #     print(f"{ts.astimezone(local_tz):%H}h --> {price:.5f} ")
    ts_loc_18h_utc = datetime(2021, 6, 1, 18, tzinfo=local_tz).astimezone(UTC_TZ)
    price_loc_18h = pvpc_data._current_prices[ts_loc_18h_utc]
    assert price_loc_18h == expected_18h
