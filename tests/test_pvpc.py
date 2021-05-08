"""Tests for aiopvpc."""
import logging
from asyncio import TimeoutError
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytz
from aiohttp import ClientError

from aiopvpc import ESIOS_TARIFFS, PVPCData, REFERENCE_TZ
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
@pytest.mark.asyncio
async def test_price_extract(
    day_str, num_prices, num_calls, num_prices_8h, available_8h
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str)
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        local_timezone=_TZ_TEST, tariff="discrimination", websession=mock_session,
    )

    pvpc_data.source_available = True
    assert not pvpc_data.process_state_and_attributes(day)

    await pvpc_data.async_update_prices(day)
    has_prices = pvpc_data.process_state_and_attributes(day)
    assert len(pvpc_data._current_prices) == num_prices
    assert mock_session.call_count == num_calls
    assert has_prices

    has_prices = pvpc_data.process_state_and_attributes(day + timedelta(hours=10))
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
@pytest.mark.asyncio
async def test_bad_downloads(
    available, day_str, num_log_msgs, status, exception, caplog,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(day_str)
    mock_session = MockAsyncSession(status=status, exc=exception)
    with caplog.at_level(logging.DEBUG):
        pvpc_data = PVPCData(
            local_timezone=REFERENCE_TZ, tariff="normal", websession=mock_session,
        )
        pvpc_data.source_available = available
        assert not pvpc_data.process_state_and_attributes(day)
        prices = await pvpc_data.async_update_prices(day)
        assert not prices
        assert not pvpc_data.process_state_and_attributes(day)
        assert len(caplog.messages) == num_log_msgs
    assert mock_session.call_count == 1
    assert len(prices) == 0


def test_full_data_download_range():
    """Test retrieval of full PVPC data in a day range."""
    start = _TZ_TEST.localize(datetime(2019, 10, 26, 15))
    end = _TZ_TEST.localize(datetime(2019, 10, 27, 13))

    with patch("aiohttp.ClientSession", MockAsyncSession):
        pvpc_data = PVPCData()
        prices = pvpc_data.download_prices_for_range(start, end)

    assert len(prices) == 24
    first_price = min(prices)
    last_price = max(prices)
    assert first_price.hour == 14 and first_price.tzname() == "UTC"
    assert last_price.hour == 13 and last_price.tzname() == "UTC"
    data_first_hour = prices[first_price]

    # Check full PVPC data is retrieved
    assert len(data_first_hour) == 30
    assert all(tag in data_first_hour for tag in ESIOS_TARIFFS)

    # Check units have not changed in full data retrieval (they are in €/MWh)
    assert all(data_first_hour[tag] > 1 for tag in ESIOS_TARIFFS)


@pytest.mark.asyncio
async def test_download_range(caplog):
    """Test retrieval of full PVPC data in a day range."""
    start = datetime(2019, 10, 26, 15)
    end = datetime(2019, 10, 28, 13)
    mock_session = MockAsyncSession()

    with caplog.at_level(logging.WARNING):
        pvpc_data = PVPCData(
            tariff="electric_car", local_timezone=_TZ_TEST, websession=mock_session
        )
        prices = await pvpc_data.async_download_prices_for_range(start, end)
        assert mock_session.call_count == 3
        assert len(prices) == 33
        assert len(caplog.messages) == 2

        no_prices = await pvpc_data.async_download_prices_for_range(
            datetime(2010, 8, 26, 23), datetime(2010, 8, 27, 22)
        )
        assert len(no_prices) == 0
        assert len(caplog.messages) == 4

    first_price = min(prices)
    assert first_price.hour == 14 and first_price.tzname() == "UTC"
    # Check only tariff values are retrieved
    assert isinstance(prices[first_price], float)
    assert prices[first_price] < 1
