"""Tests for aiopvpc."""

import logging
from asyncio import TimeoutError
from datetime import datetime, timedelta
from typing import cast

import pytest
from aiohttp import ClientError

from aiopvpc.const import (
    ALL_SENSORS,
    ATTRIBUTIONS,
    DataSource,
    KEY_INJECTION,
    KEY_OMIE,
    KEY_PVPC,
    REFERENCE_TZ,
    UTC_TZ,
)
from aiopvpc.pvpc_data import BadApiTokenAuthError, PVPCData
from tests.conftest import check_num_datapoints, MockAsyncSession, run_h_step, TZ_TEST


@pytest.mark.parametrize(
    "data_source, api_token, day_str, num_log_msgs, status, exception",
    (
        ("esios_public", None, "2032-10-26", 0, 200, None),
        ("esios_public", None, "2032-10-26", 1, 500, None),
        ("esios", "bad-token", "2032-10-26", 1, 403, None),
        ("esios", "bad-token", "2032-10-26", 1, 401, None),
        ("esios_public", None, "2032-10-26", 1, 200, TimeoutError),
        ("esios_public", None, "2032-10-26", 1, 200, ClientError),
    ),
)
@pytest.mark.asyncio
async def test_bad_downloads(
    data_source,
    api_token,
    day_str,
    num_log_msgs,
    status,
    exception,
    caplog,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str).astimezone(REFERENCE_TZ)
    mock_session = MockAsyncSession(status=status, exc=exception)
    with caplog.at_level(logging.INFO):
        pvpc_data = PVPCData(
            session=mock_session,
            data_source=cast(DataSource, data_source),
            api_token=api_token,
        )
        if status in (401, 403):
            with pytest.raises(BadApiTokenAuthError):
                await pvpc_data.async_update_all(None, day)
            assert mock_session.call_count == 1
            return

        api_data = await pvpc_data.async_update_all(None, day)
        assert not api_data.sensors[KEY_PVPC]
        assert not pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, day)
        assert len(caplog.messages) == num_log_msgs
    assert mock_session.call_count == 1
    check_num_datapoints(api_data, (KEY_PVPC,), 0)


# TODO review download schedule for Canary Islands TZ
@pytest.mark.parametrize(
    "local_tz, data_source, sensor_keys",
    (
        (TZ_TEST, "esios_public", (KEY_PVPC,)),
        (REFERENCE_TZ, "esios_public", (KEY_PVPC,)),
        (TZ_TEST, "esios", (KEY_PVPC, KEY_INJECTION, KEY_OMIE)),
        (REFERENCE_TZ, "esios", (KEY_PVPC, KEY_INJECTION, KEY_OMIE)),
    ),
)
@pytest.mark.asyncio
async def test_reduced_api_download_rate_dst_change(local_tz, data_source, sensor_keys):
    """Test time evolution and number of API calls."""
    start = datetime(2021, 10, 30, 15, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        local_timezone=local_tz,
        data_source=cast(DataSource, data_source),
        api_token="test-token" if data_source == "esios" else None,
        sensor_keys=sensor_keys,
    )
    assert pvpc_data.attribution == ATTRIBUTIONS[data_source]

    # avoid extra calls at day if already got all today prices
    api_data = None
    for _ in range(3):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == len(sensor_keys)
        check_num_datapoints(api_data, sensor_keys, 24)
    assert all(api_data.availability.values())

    # first call for next-day prices
    assert start == datetime(2021, 10, 30, 18, tzinfo=UTC_TZ)
    start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 2 * len(sensor_keys)
    check_num_datapoints(api_data, sensor_keys, 49)

    # avoid calls at evening if already got all today+tomorrow prices
    for _ in range(3):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == 2 * len(sensor_keys)
        check_num_datapoints(api_data, sensor_keys, 49)

    # avoid calls at day if already got all today prices
    for _ in range(21):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == 2 * len(sensor_keys)
        assert all(api_data.availability.values())
        # check_num_datapoints(api_data, sensor_keys, 25)

    # call for next-day prices (no more available)
    assert start == datetime(2021, 10, 31, 19, tzinfo=UTC_TZ)
    call_count = mock_session.call_count
    while start.astimezone(local_tz) <= datetime(2021, 10, 31, 23, tzinfo=local_tz):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
        call_count += len(sensor_keys)
        assert mock_session.call_count == call_count
        # check_num_datapoints(api_data, sensor_keys, 25)

    # assert mock_session.call_count == 6
    assert pvpc_data.states.get(KEY_PVPC)
    assert all(api_data.availability.values())
    assert start.astimezone(local_tz) == datetime(2021, 11, 1, tzinfo=local_tz)
    assert not pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)

    # After known prices are exausted, the state is flagged as unavailable
    with pytest.raises(AssertionError):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert not any(api_data.availability.values())
    start += timedelta(hours=1)
    assert not pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)


@pytest.mark.parametrize(
    "local_tz, data_source, sensor_keys",
    (
        (TZ_TEST, "esios", ALL_SENSORS),
        (REFERENCE_TZ, "esios", ALL_SENSORS),
    ),
)
@pytest.mark.asyncio
async def test_reduced_api_download_rate(local_tz, data_source, sensor_keys):
    """Test time evolution and number of API calls."""
    start = datetime(2024, 3, 9, 2, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        local_timezone=local_tz,
        data_source=cast(DataSource, data_source),
        api_token="test-token" if data_source == "esios" else None,
        sensor_keys=sensor_keys,
    )
    assert pvpc_data.attribution == ATTRIBUTIONS[data_source]

    # avoid extra calls at day if already got all today prices
    api_data = None
    for _ in range(17):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == len(sensor_keys)
        check_num_datapoints(api_data, sensor_keys, 24)

    # first call for next-day prices
    assert start == datetime(2024, 3, 9, 19, tzinfo=UTC_TZ)
    start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 2 * len(sensor_keys)
    check_num_datapoints(api_data, sensor_keys, 24)

    call_count = mock_session.call_count
    while start.astimezone(local_tz) <= datetime(2024, 3, 9, 23, tzinfo=local_tz):
        start, api_data = await run_h_step(mock_session, pvpc_data, api_data, start)
        call_count += len(sensor_keys)
        assert mock_session.call_count == call_count
        check_num_datapoints(api_data, sensor_keys, 24)
