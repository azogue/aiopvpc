"""Tests for aiopvpc."""
import logging
from asyncio import TimeoutError
from datetime import datetime, timedelta

import pytest
import pytz
from aiohttp import ClientError

from aiopvpc import PVPCData, REFERENCE_TZ
from .conftest import MockAsyncSession

_TZ_TEST = pytz.timezone("Atlantic/Canary")


@pytest.mark.parametrize(
    "day_str, num_prices, num_calls, num_prices_8h, available_8h",
    (
        ("2019-10-26 00:00:00+00:00", 24, 1, 24, True),
        ("2019-10-27 00:00:00+00:00", 25, 1, 25, True),
        ("2019-03-31 20:00:00+00:00", 23, 2, 23, False),
        ("2019-10-26 21:00:00+00:00", 49, 2, 24, True),
    ),
)
async def test_price_extract(
    day_str, num_prices, num_calls, num_prices_8h, available_8h
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str).astimezone(pytz.UTC)
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        local_timezone=_TZ_TEST,
        tariff="discrimination",
        websession=mock_session,
    )

    pvpc_data.source_available = True
    has_prices = pvpc_data.process_state_and_attributes(day)
    assert not has_prices

    prices = await pvpc_data.async_update_prices(day)
    has_prices = pvpc_data.process_state_and_attributes(day)
    assert len(prices) == num_prices
    assert mock_session.call_count == num_calls
    assert has_prices

    has_prices = pvpc_data.process_state_and_attributes(
        day + timedelta(hours=8)
    )
    assert len(pvpc_data._current_prices) == num_prices_8h
    assert has_prices == available_8h


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
async def test_bad_downloads(
    available, day_str, num_log_msgs, status, exception, caplog,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str).astimezone(pytz.UTC)
    mock_session = MockAsyncSession(status=status, exc=exception)
    with caplog.at_level(logging.DEBUG):
        pvpc_data = PVPCData(
            local_timezone=REFERENCE_TZ,
            tariff="discrimination",
            websession=mock_session,
        )
        pvpc_data.source_available = available
        has_prices = pvpc_data.process_state_and_attributes(day)
        assert not has_prices

        prices = await pvpc_data.async_update_prices(day)
        has_prices = pvpc_data.process_state_and_attributes(day)
        assert not has_prices
        assert len(caplog.messages) == num_log_msgs
    assert mock_session.call_count == 1
    assert len(prices) == 0
