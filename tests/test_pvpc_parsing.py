"""Tests for aiopvpc."""
from datetime import datetime, timedelta
from typing import cast

import pytest

from aiopvpc.const import (
    ALL_SENSORS,
    DataSource,
    KEY_INJECTION,
    KEY_MAG,
    KEY_OMIE,
    KEY_PVPC,
    REFERENCE_TZ,
    SENSOR_KEY_TO_DATAID,
)
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "ts, source, timezone, n_prices, n_calls, n_prices_8h, available_8h",
    (
        ("2021-06-01 09:00:00", "esios", REFERENCE_TZ, 24, 1, 24, True),
        ("2021-06-01 09:00:00", "esios", TZ_TEST, 24, 1, 24, True),
        ("2023-01-06 09:00:00", "esios", REFERENCE_TZ, 24, 1, 24, True),
        ("2023-01-06 09:00:00", "esios", TZ_TEST, 24, 1, 24, True),
        ("2021-10-30 00:00:00+08:00", "esios_public", TZ_TEST, 0, 1, 0, False),
        ("2021-10-30 00:00:00", "esios_public", TZ_TEST, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "esios_public", TZ_TEST, 25, 1, 25, True),
        ("2022-03-27 20:00:00", "esios_public", TZ_TEST, 23, 2, 23, False),
        ("2022-03-27 20:00:00+04:00", "esios_public", TZ_TEST, 23, 1, 23, False),
        ("2021-10-30 21:00:00", "esios_public", TZ_TEST, 49, 2, 26, True),
        ("2021-10-30 21:00:00+01:00", "esios_public", TZ_TEST, 49, 2, 26, True),
        ("2021-10-30 00:00:00", "esios_public", REFERENCE_TZ, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "esios_public", REFERENCE_TZ, 25, 1, 25, True),
        ("2022-03-27 20:00:00", "esios_public", REFERENCE_TZ, 23, 2, 23, False),
        ("2021-10-30 21:00:00", "esios_public", REFERENCE_TZ, 49, 2, 25, True),
        ("2021-06-01 09:00:00", "esios_public", REFERENCE_TZ, 24, 1, 24, True),
        ("2021-06-01 09:00:00", "esios_public", TZ_TEST, 24, 1, 24, True),
    ),
)
@pytest.mark.asyncio
async def test_price_extract(
    ts,
    source,
    timezone,
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
        data_source=cast(DataSource, source),
        api_token="test-token" if source == "esios" else None,
    )

    api_data = await pvpc_data.async_update_all(None, day)
    pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, day)
    assert len(api_data.sensors[KEY_PVPC]) == n_prices
    assert mock_session.call_count == n_calls
    assert len(api_data.sensors) == 1

    has_prices = pvpc_data.process_state_and_attributes(
        api_data, KEY_PVPC, day + timedelta(hours=10)
    )
    assert len(api_data.sensors[KEY_PVPC]) == n_prices_8h
    assert has_prices == available_8h
    if has_prices:
        last_dt, last_p = list(api_data.sensors[KEY_PVPC].items())[-1]
        assert last_dt.astimezone(timezone).hour == 23


@pytest.mark.asyncio
async def test_price_sensor_attributes():
    """Test data parsing of official API files."""
    day = datetime.fromisoformat("2023-01-06 09:00:00")
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        api_token="test-token",
        sensor_keys=ALL_SENSORS,
    )

    api_data = await pvpc_data.async_update_all(None, day)
    for key in ALL_SENSORS:
        pvpc_data.process_state_and_attributes(api_data, key, day)
    assert len(api_data.sensors[KEY_PVPC]) == 24
    assert mock_session.call_count == 4
    assert len(api_data.sensors) == 4

    ref_data = {
        KEY_PVPC: {"hours_to_better_price": 1, "num_better_prices_ahead": 6},
        KEY_INJECTION: {"hours_to_better_price": 5, "num_better_prices_ahead": 5},
        KEY_MAG: {"hours_to_better_price": 1, "num_better_prices_ahead": 7},
        KEY_OMIE: {"hours_to_better_price": 1, "num_better_prices_ahead": 6},
    }

    for key in ALL_SENSORS:
        has_prices = pvpc_data.process_state_and_attributes(
            api_data, key, day + timedelta(hours=2)
        )
        assert has_prices, key
        assert api_data.availability[key]
        last_dt, last_p = list(api_data.sensors[key].items())[-1]
        assert last_dt.astimezone(REFERENCE_TZ).hour == 23

        current_price = pvpc_data.states[key]
        sensor_attrs = pvpc_data.sensor_attributes[key]
        assert sensor_attrs["sensor_id"] == key
        assert sensor_attrs["data_id"] == SENSOR_KEY_TO_DATAID[key]
        assert sensor_attrs["price_12h"] == current_price
        prices_ahead = [sensor_attrs[f"price_{h:02}h"] for h in range(13, 24)]
        assert len(prices_ahead) == 11
        assert sensor_attrs["price_23h"] == last_p
        assert sensor_attrs["min_price"] == min(api_data.sensors[key].values())
        assert sensor_attrs["max_price"] == max(api_data.sensors[key].values())
        key_min_at = f'price_{sensor_attrs["min_price_at"]:02d}h'
        assert sensor_attrs[key_min_at] == min(api_data.sensors[key].values())
        key_max_at = f'price_{sensor_attrs["max_price_at"]:02d}h'
        assert sensor_attrs[key_max_at] == max(api_data.sensors[key].values())
        assert (
            sensor_attrs["hours_to_better_price"]
            == ref_data[key]["hours_to_better_price"]
        )
        assert (
            sensor_attrs["num_better_prices_ahead"]
            == ref_data[key]["num_better_prices_ahead"]
        )
        key_next = f'price_{12 + sensor_attrs["hours_to_better_price"]}h'
        if key == KEY_INJECTION:
            assert sensor_attrs[key_next] > current_price
            num_better = sum(1 for p in prices_ahead if p > current_price)
        else:
            assert sensor_attrs[key_next] < current_price
            num_better = sum(1 for p in prices_ahead if p < current_price)
        assert num_better == sensor_attrs["num_better_prices_ahead"]
