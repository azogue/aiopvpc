"""Tests for aiopvpc."""
import logging
from asyncio import TimeoutError
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from aiohttp import ClientError

from aiopvpc import ESIOS_TARIFFS, PVPCData, REFERENCE_TZ
from .conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "day_str, timezone, num_prices, num_calls, num_prices_8h, available_8h, last_hour",
    (
        ("2019-10-26 00:00:00+08:00", TZ_TEST, 0, 1, 0, False, None),
        ("2019-10-26 00:00:00", TZ_TEST, 24, 1, 24, True, 23),
        ("2019-10-27 00:00:00", TZ_TEST, 25, 1, 25, True, 23),
        ("2019-03-31 20:00:00", TZ_TEST, 23, 2, 23, False, 23),
        ("2019-03-31 20:00:00+04:00", TZ_TEST, 23, 1, 23, False, 23),
        ("2019-10-26 21:00:00", TZ_TEST, 49, 2, 26, True, 23),
        ("2019-10-26 21:00:00+01:00", TZ_TEST, 49, 2, 26, True, 23),
        ("2019-10-26 00:00:00", REFERENCE_TZ, 24, 1, 24, True, 23),
        ("2019-10-27 00:00:00", REFERENCE_TZ, 25, 1, 25, True, 23),
        ("2019-03-31 20:00:00", REFERENCE_TZ, 23, 2, 23, False, 23),
        ("2019-10-26 21:00:00", REFERENCE_TZ, 49, 2, 25, True, 23),
        ("2021-06-01 06:00:00", REFERENCE_TZ, 24, 1, 24, True, 23),
    ),
)
@pytest.mark.asyncio
async def test_price_extract(
    day_str, timezone, num_prices, num_calls, num_prices_8h, available_8h, last_hour
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str)
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        local_timezone=timezone,
        tariff="discrimination",
        websession=mock_session,
    )

    pvpc_data.source_available = True
    assert not pvpc_data.process_state_and_attributes(day)
    assert mock_session.call_count == 0

    await pvpc_data.async_update_prices(day)
    has_prices = pvpc_data.process_state_and_attributes(day)
    assert len(pvpc_data._current_prices) == num_prices
    assert mock_session.call_count == num_calls

    has_prices = pvpc_data.process_state_and_attributes(day + timedelta(hours=10))
    assert len(pvpc_data._current_prices) == num_prices_8h
    assert has_prices == available_8h
    if has_prices:
        last_dt, last_p = list(pvpc_data._current_prices.items())[-1]
        assert last_dt.astimezone(timezone).hour == last_hour


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
            local_timezone=REFERENCE_TZ,
            tariff="normal",
            websession=mock_session,
        )
        pvpc_data.source_available = available
        assert not pvpc_data.process_state_and_attributes(day)
        prices = await pvpc_data.async_update_prices(day)
        assert not prices
        assert not pvpc_data.process_state_and_attributes(day)
        assert len(caplog.messages) == num_log_msgs
    assert mock_session.call_count == 1
    assert len(prices) == 0


@pytest.mark.parametrize(
    "timezone, start, end",
    (
        (
            TZ_TEST,
            datetime(2019, 10, 26, 15, tzinfo=TZ_TEST),
            datetime(2019, 10, 27, 13, tzinfo=TZ_TEST),
        ),
        (
            REFERENCE_TZ,
            datetime(2019, 10, 26, 15, tzinfo=REFERENCE_TZ),
            datetime(2019, 10, 27, 13, tzinfo=REFERENCE_TZ),
        ),
    ),
)
def test_full_data_download_range(timezone, start, end):
    """Test retrieval of full PVPC data in a day range."""
    with patch("aiohttp.ClientSession", MockAsyncSession):
        pvpc_data = PVPCData(local_timezone=timezone)
        prices = pvpc_data.download_prices_for_range(start, end)

    assert len(prices) == 24
    first_price = min(prices)
    last_price = max(prices)
    data_first_hour = prices[first_price]

    # Check full PVPC data is retrieved
    assert len(data_first_hour) == 30
    assert all(tag in data_first_hour for tag in ESIOS_TARIFFS)

    # Check units have not changed in full data retrieval (they are in €/MWh)
    assert all(data_first_hour[tag] > 1 for tag in ESIOS_TARIFFS)

    # check tz-alignment (price at 15h is tz-independent)
    assert prices[first_price]["NOC"] == 119.16
    assert first_price.astimezone(timezone).hour == 15
    assert last_price.astimezone(timezone).hour == 13


@pytest.mark.asyncio
async def test_download_range(caplog):
    """Test retrieval of full PVPC data in a day range."""
    start = datetime(2019, 10, 26, 15)
    end = datetime(2019, 10, 28, 13)
    mock_session = MockAsyncSession()

    with caplog.at_level(logging.WARNING):
        pvpc_data = PVPCData(
            tariff="electric_car", local_timezone=TZ_TEST, websession=mock_session
        )
        prices = await pvpc_data.async_download_prices_for_range(start, end)
        assert mock_session.call_count == 3
        assert len(prices) == 34
        assert len(caplog.messages) == 2

        no_prices = await pvpc_data.async_download_prices_for_range(
            datetime(2010, 8, 27, tzinfo=TZ_TEST),
            datetime(2010, 8, 27, 22, tzinfo=TZ_TEST),
        )
        assert len(no_prices) == 0
        assert len(caplog.messages) == 4
        assert not await pvpc_data.async_download_prices_for_range(
            datetime(2010, 8, 27), datetime(2010, 8, 27, 23)
        )
        assert len(caplog.messages) == 7

    first_price = min(prices)
    assert first_price.hour == 14 and first_price.tzname() == "UTC"
    # Check only tariff values are retrieved
    assert isinstance(prices[first_price], float)
    assert prices[first_price] < 1
