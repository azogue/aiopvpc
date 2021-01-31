"""Tests for aiopvpc."""
from datetime import datetime

import pytest
import pytz
from aiohttp import ClientSession

from aiopvpc import PVPCData

_TZ_TEST = pytz.timezone("Atlantic/Canary")


@pytest.mark.skip("Real call to ESIOS API")
def test_real_download_range():
    # No async
    pvpc_handler = PVPCData("normal")
    start = datetime(2019, 10, 26, 15)
    end = datetime(2019, 10, 28, 13)
    prices = pvpc_handler.download_prices_for_range(start, end)
    assert len(prices) == 48

    no_prices = pvpc_handler.download_prices_for_range(
        datetime(2010, 8, 26, 23), datetime(2010, 8, 27, 22)
    )
    assert len(no_prices) == 0


@pytest.mark.skip("Real call to ESIOS API")
async def test_real_download_range_async():
    start = datetime(2019, 10, 26, 15)
    end = datetime(2019, 10, 28, 13)
    async with ClientSession() as session:
        pvpc_handler = PVPCData("normal", websession=session)
        prices = await pvpc_handler.async_download_prices_for_range(start, end)
    assert len(prices) == 48

    # without session also works, creating one for each download range call
    pvpc_handler_no_s = PVPCData("normal")
    prices2 = await pvpc_handler_no_s.async_download_prices_for_range(start, end)
    assert len(prices2) == 48
    assert prices == prices2


@pytest.mark.skip("Real call to ESIOS API")
async def test_real_download_today_async():
    async with ClientSession() as session:
        pvpc_handler = PVPCData("discriminacion", websession=session)
        prices = await pvpc_handler.async_update_prices(datetime.utcnow())
    assert 22 < len(prices) < 49

    # Check error without session
    pvpc_handler_bad = PVPCData("discriminacion")
    with pytest.raises(AssertionError):
        await pvpc_handler_bad.async_update_prices(datetime.utcnow())
