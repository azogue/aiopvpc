"""Tests for aiopvpc."""
from __future__ import annotations

import logging
from datetime import datetime

import pytest

from aiopvpc.const import (
    ALL_SENSORS,
    KEY_INYECTION,
    KEY_MAG,
    KEY_OMIE,
    KEY_PVPC,
    TARIFFS,
    UTC_TZ,
)
from aiopvpc.ha_helpers import get_enabled_sensor_keys, make_sensor_unique_id
from aiopvpc.pvpc_data import BadApiTokenAuthError, PVPCData
from tests.conftest import check_num_datapoints, MockAsyncSession, run_h_step


def test_sensor_unique_ids():
    all_sensor_keys = get_enabled_sensor_keys(
        using_private_api=False, disabled_sensor_ids=[]
    )
    assert all_sensor_keys == {KEY_PVPC}

    all_sensor_keys = get_enabled_sensor_keys(
        using_private_api=True, disabled_sensor_ids=[]
    )
    assert sorted(all_sensor_keys) == sorted(ALL_SENSORS)
    counter_combs = 0
    unique_ids = set()
    for tariff in TARIFFS:
        for key in all_sensor_keys:
            unique_ids.add(
                make_sensor_unique_id(config_entry_id=tariff, sensor_key=key)
            )
            counter_combs += 1
    assert counter_combs == len(unique_ids)

    assert not get_enabled_sensor_keys(
        using_private_api=True, disabled_sensor_ids=list(unique_ids)
    )


@pytest.mark.asyncio
async def test_disable_sensors():
    start = datetime(2023, 1, 6, 19, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    sensor_keys = ALL_SENSORS
    assert len(sensor_keys) == 4
    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        data_source="esios",
        api_token="test-token",
        sensor_keys=sensor_keys,
    )

    api_data = None
    start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 8
    check_num_datapoints(api_data, sensor_keys, 24)

    pvpc_data.update_active_sensors(KEY_PVPC, enabled=False)
    pvpc_data.update_active_sensors(KEY_OMIE, enabled=False)
    pvpc_data.update_active_sensors(KEY_MAG, enabled=False)
    pvpc_data.update_active_sensors(KEY_MAG, enabled=False)

    start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 9
    check_num_datapoints(api_data, sensor_keys, 24)
    logging.error(api_data.sensors.keys())

    pvpc_data.update_active_sensors(KEY_INYECTION, enabled=False)
    start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 9
    check_num_datapoints(api_data, sensor_keys, 24)

    start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 9
    check_num_datapoints(api_data, sensor_keys, 24)

    start, api_data = await run_h_step(
        mock_session, pvpc_data, api_data, start, should_fail=True
    )
    assert mock_session.call_count == 9
    # check_num_datapoints(api_data, sensor_keys, 0)

    pvpc_data.update_active_sensors(KEY_INYECTION, enabled=True)
    pvpc_data.update_active_sensors(KEY_PVPC, enabled=True)
    start, api_data = await run_h_step(
        mock_session, pvpc_data, api_data, start, should_fail=True
    )
    assert mock_session.call_count == 11

    pvpc_data.update_active_sensors(KEY_INYECTION, enabled=True)
    pvpc_data.update_active_sensors(KEY_PVPC, enabled=True)
    pvpc_data.update_active_sensors(KEY_MAG, enabled=True)
    pvpc_data.update_active_sensors(KEY_OMIE, enabled=True)
    await run_h_step(mock_session, pvpc_data, api_data, start, should_fail=True)
    assert mock_session.call_count == 15


@pytest.mark.asyncio
async def test_check_api_token():
    start = datetime(2023, 1, 6, 19, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession(status=401)
    pvpc_data = PVPCData(session=mock_session)
    token_ok = await pvpc_data.check_api_token(start, "bad_token")
    assert not token_ok
    assert mock_session.call_count == 1

    with pytest.raises(BadApiTokenAuthError):
        await pvpc_data.async_update_all(None, start)
    assert mock_session.call_count == 2

    mock_session_ok = MockAsyncSession()
    pvpc_data_ok = PVPCData(
        session=mock_session_ok,
        data_source="esios",
        api_token="good_token",
    )
    token_ok = await pvpc_data_ok.check_api_token(start)
    assert token_ok
    assert mock_session_ok.call_count == 1
