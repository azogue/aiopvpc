"""Tests for aiopvpc."""
import logging
from asyncio import TimeoutError
from datetime import datetime, timedelta

import pytest
from aiohttp import ClientError

from aiopvpc.const import REFERENCE_TZ, UTC_TZ
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "day_str, timezone, zone_cm, num_prices, num_calls, num_prices_8h, available_8h",
    (
        ("2021-10-30 00:00:00+08:00", TZ_TEST, False, 0, 1, 0, False),
        ("2021-10-30 00:00:00", TZ_TEST, False, 24, 1, 24, True),
        ("2021-10-31 00:00:00", TZ_TEST, False, 25, 1, 25, True),
        ("2022-03-27 20:00:00", TZ_TEST, False, 23, 2, 23, False),
        ("2022-03-27 20:00:00+04:00", TZ_TEST, False, 23, 1, 23, False),
        ("2021-10-30 21:00:00", TZ_TEST, False, 49, 2, 26, True),
        ("2021-10-30 21:00:00+01:00", TZ_TEST, False, 49, 2, 26, True),
        ("2021-10-30 00:00:00", REFERENCE_TZ, True, 24, 1, 24, True),
        ("2021-10-31 00:00:00", REFERENCE_TZ, True, 25, 1, 25, True),
        ("2022-03-27 20:00:00", REFERENCE_TZ, True, 23, 2, 23, False),
        ("2021-10-30 21:00:00", REFERENCE_TZ, True, 49, 2, 25, True),
        ("2021-06-01 09:00:00", REFERENCE_TZ, True, 24, 1, 24, True),
    ),
)
@pytest.mark.asyncio
async def test_price_extract(
    day_str,
    timezone,
    zone_cm,
    num_prices,
    num_calls,
    num_prices_8h,
    available_8h,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str)
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        tariff="2.0TD",
        local_timezone=timezone,
        websession=mock_session,
        zone_ceuta_melilla=zone_cm,
    )

    pvpc_data.source_available = True
    assert not pvpc_data.process_state_and_attributes(day)
    assert mock_session.call_count == 0

    await pvpc_data.async_update_prices(day)
    pvpc_data.process_state_and_attributes(day)
    assert len(pvpc_data._current_prices) == num_prices
    assert mock_session.call_count == num_calls

    has_prices = pvpc_data.process_state_and_attributes(day + timedelta(hours=10))
    assert len(pvpc_data._current_prices) == num_prices_8h
    assert has_prices == available_8h
    if has_prices:
        last_dt, last_p = list(pvpc_data._current_prices.items())[-1]
        assert last_dt.astimezone(timezone).hour == 23


@pytest.mark.parametrize(
    "available, day_str, num_log_msgs, status, exception",
    (
        (False, "2032-10-26 00:00:00+00:00", 0, 200, None),
        (False, "2032-10-26 00:00:00+00:00", 0, 500, None),
        (True, "2032-10-26 00:00:00+00:00", 1, 200, TimeoutError),
        (False, "2032-10-26 00:00:00+00:00", 0, 200, TimeoutError),
        (True, "2032-10-26 00:00:00+00:00", 1, 200, ClientError),
        (False, "2032-10-26 00:00:00+00:00", 0, 200, ClientError),
    ),
)
@pytest.mark.asyncio
async def test_bad_downloads(
    available,
    day_str,
    num_log_msgs,
    status,
    exception,
    caplog,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str)
    mock_session = MockAsyncSession(status=status, exc=exception)
    with caplog.at_level(logging.INFO):
        pvpc_data = PVPCData(
            websession=mock_session,
            tariff="2.0TD",
            local_timezone=REFERENCE_TZ,
        )
        pvpc_data.source_available = available
        assert not pvpc_data.process_state_and_attributes(day)
        prices = await pvpc_data.async_update_prices(day)
        assert not prices
        assert not pvpc_data.process_state_and_attributes(day)
        assert len(caplog.messages) == num_log_msgs
    assert mock_session.call_count == 1
    assert len(prices) == 0


async def _run_h_step(
    mock_session: MockAsyncSession, pvpc_data: PVPCData, start: datetime
):
    if pvpc_data._current_prices:
        logging.debug(
            "[Calls=%d]-> start=%s --> %s -> %s (%d prices)",
            mock_session.call_count,
            start,
            list(pvpc_data._current_prices)[0].strftime("%Y-%m-%d %Hh"),
            list(pvpc_data._current_prices)[-1].strftime("%Y-%m-%d %Hh"),
            len(pvpc_data._current_prices),
        )
    await pvpc_data.async_update_prices(start)
    assert pvpc_data.process_state_and_attributes(start)
    start += timedelta(hours=1)
    return start, pvpc_data._current_prices


# TODO review download schedule for Canary Islands TZ
@pytest.mark.parametrize("local_tz", (TZ_TEST, REFERENCE_TZ))
@pytest.mark.asyncio
async def test_reduced_api_download_rate(local_tz):
    """Test time evolution and number of API calls."""
    start = datetime(2021, 10, 30, 15, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    # logging.critical(local_tz)
    pvpc_data = PVPCData(
        websession=mock_session, tariff="2.0TD", local_timezone=local_tz
    )

    # avoid extra calls at day if already got all today prices
    for _ in range(3):
        start, prices = await _run_h_step(mock_session, pvpc_data, start)
        assert mock_session.call_count == 1
        assert len(prices) == 24

    # first call for next-day prices
    assert start == datetime(2021, 10, 30, 18, tzinfo=UTC_TZ)
    start, prices = await _run_h_step(mock_session, pvpc_data, start)
    assert mock_session.call_count == 2
    assert len(prices) == 49

    # avoid calls at evening if already got all today+tomorrow prices
    for _ in range(3):
        start, prices = await _run_h_step(mock_session, pvpc_data, start)
        assert mock_session.call_count == 2
        assert len(prices) == 49

    # avoid calls at day if already got all today prices
    for _ in range(21):
        start, prices = await _run_h_step(mock_session, pvpc_data, start)
        assert mock_session.call_count == 2
        assert pvpc_data.state_available
        # assert len(prices) == 25

    # call for next-day prices (no more available)
    assert start == datetime(2021, 10, 31, 19, tzinfo=UTC_TZ)
    call_count = mock_session.call_count
    while start.astimezone(local_tz) <= datetime(2021, 10, 31, 23, tzinfo=local_tz):
        start, prices = await _run_h_step(mock_session, pvpc_data, start)
        call_count += 1
        assert mock_session.call_count == call_count
        # assert len(prices) == 25

    # assert mock_session.call_count == 6
    assert pvpc_data.state
    assert pvpc_data.state_available
    assert start.astimezone(local_tz) == datetime(2021, 11, 1, tzinfo=local_tz)
    assert not pvpc_data.process_state_and_attributes(start)

    # After known prices are exausted, the state is flagged as unavailable
    with pytest.raises(AssertionError):
        await _run_h_step(mock_session, pvpc_data, start)
    assert not pvpc_data.state_available
    start += timedelta(hours=1)
    assert not pvpc_data.process_state_and_attributes(start)
