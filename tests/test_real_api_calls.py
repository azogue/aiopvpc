"""Tests for aiopvpc."""
from datetime import datetime

import pytest
from aiohttp import ClientSession

from aiopvpc import PVPCData


@pytest.mark.real_api_call
@pytest.mark.asyncio
async def test_real_download_today_async():
    async with ClientSession() as session:
        pvpc_handler = PVPCData("discrimination", websession=session)
        prices = await pvpc_handler.async_update_prices(datetime.utcnow())
    assert 22 < len(prices) < 49

    # Check error without session
    pvpc_handler_bad = PVPCData("2.0TD")
    with pytest.raises(AssertionError):
        await pvpc_handler_bad.async_update_prices(datetime.utcnow())
