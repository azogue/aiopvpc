"""Tests for aiopvpc."""
from __future__ import annotations

import logging
from asyncio import TimeoutError
from datetime import datetime, timedelta
from typing import cast

import pytest
from aiohttp import ClientError

from aiopvpc.const import (
    ALL_SENSORS,
    DataSource,
    EsiosApiData,
    KEY_PVPC,
    REFERENCE_TZ,
    UTC_TZ,
)
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "data_source, api_token, day_str, num_log_msgs, status, exception",
    (
        ("esios_public", None, "2032-10-26", 0, 200, None),
        ("esios_public", None, "2032-10-26", 1, 500, None),
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

        api_data = await pvpc_data.async_update_all(None, day)
        assert not api_data["sensors"][KEY_PVPC]
        assert not pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, day)
        assert len(caplog.messages) == num_log_msgs
    assert mock_session.call_count == 1
    assert len(api_data["sensors"][KEY_PVPC]) == 0


async def _run_h_step(
    mock_session: MockAsyncSession,
    pvpc_data: PVPCData,
    api_data: EsiosApiData | None,
    start: datetime,
) -> tuple[datetime, EsiosApiData]:
    current_prices = api_data["sensors"][KEY_PVPC] if api_data else {}
    if current_prices:
        logging.debug(
            "[Calls=%d]-> start=%s --> %s -> %s (%d prices)",
            mock_session.call_count,
            start,
            list(current_prices)[0].strftime("%Y-%m-%d %Hh"),
            list(current_prices)[-1].strftime("%Y-%m-%d %Hh"),
            len(current_prices),
        )
    api_data = await pvpc_data.async_update_all(api_data, start)
    assert pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)
    start += timedelta(hours=1)
    return start, api_data


# TODO review download schedule for Canary Islands TZ
@pytest.mark.parametrize(
    "local_tz, data_source",
    (
        (TZ_TEST, "esios_public"),
        (REFERENCE_TZ, "esios_public"),
    ),
)
@pytest.mark.asyncio
async def test_reduced_api_download_rate(local_tz, data_source):
    """Test time evolution and number of API calls."""
    start = datetime(2021, 10, 30, 15, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        local_timezone=local_tz,
        data_source=cast(DataSource, data_source),
        api_token="test-token" if data_source == "esios" else None,
        sensor_keys=ALL_SENSORS if data_source == "esios" else (KEY_PVPC,),
    )

    # avoid extra calls at day if already got all today prices
    api_data = None
    for _ in range(3):
        start, api_data = await _run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == 1
        assert len(api_data["sensors"][KEY_PVPC]) == 24

    # first call for next-day prices
    assert start == datetime(2021, 10, 30, 18, tzinfo=UTC_TZ)
    start, api_data = await _run_h_step(mock_session, pvpc_data, api_data, start)
    assert mock_session.call_count == 2
    assert len(api_data["sensors"][KEY_PVPC]) == 49

    # avoid calls at evening if already got all today+tomorrow prices
    for _ in range(3):
        start, api_data = await _run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == 2
        assert len(api_data["sensors"][KEY_PVPC]) == 49

    # avoid calls at day if already got all today prices
    for _ in range(21):
        start, api_data = await _run_h_step(mock_session, pvpc_data, api_data, start)
        assert mock_session.call_count == 2
        assert api_data["available"]
        # assert len(api_data["sensors"][KEY_PVPC]) == 25

    # call for next-day prices (no more available)
    assert start == datetime(2021, 10, 31, 19, tzinfo=UTC_TZ)
    call_count = mock_session.call_count
    while start.astimezone(local_tz) <= datetime(2021, 10, 31, 23, tzinfo=local_tz):
        start, api_data = await _run_h_step(mock_session, pvpc_data, api_data, start)
        call_count += 1
        assert mock_session.call_count == call_count
        # assert len(api_data["sensors"][KEY_PVPC]) == 25

    # assert mock_session.call_count == 6
    assert pvpc_data.states.get(KEY_PVPC)
    assert api_data["available"]
    assert start.astimezone(local_tz) == datetime(2021, 11, 1, tzinfo=local_tz)
    assert not pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)

    # After known prices are exausted, the state is flagged as unavailable
    with pytest.raises(AssertionError):
        start, api_data = await _run_h_step(mock_session, pvpc_data, api_data, start)
    assert not api_data["available"]
    start += timedelta(hours=1)
    assert not pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)
