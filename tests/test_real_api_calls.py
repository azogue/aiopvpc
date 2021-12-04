"""Tests for aiopvpc."""
from datetime import datetime

import pytest
from aiohttp import ClientSession

from aiopvpc import PVPCData
from aiopvpc.const import REFERENCE_TZ
from tests.conftest import TZ_TEST


@pytest.mark.real_api_call
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data_source, tz",
    (
        ("apidatos", REFERENCE_TZ),
        ("esios_public", REFERENCE_TZ),
        ("apidatos", TZ_TEST),
        ("esios_public", TZ_TEST),
    ),
)
async def test_real_download_today_async(data_source, tz):
    async with ClientSession() as session:
        pvpc_handler = PVPCData(
            websession=session,
            tariff="2.0TD",
            data_source=data_source,
            local_timezone=tz,
        )
        prices = await pvpc_handler.async_update_prices(datetime.utcnow())
    assert 22 < len(prices) < 49
    # from pprint import pprint
    # pprint(prices)
