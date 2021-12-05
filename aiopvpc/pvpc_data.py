"""
Simple aio library to download Spanish electricity hourly prices.

Externalization of download and parsing logic for the `pvpc_hourly_pricing`
HomeAssistant integration,
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from random import random
from typing import Any, Dict, Optional, Union

import aiohttp
import async_timeout

from aiopvpc.const import (
    ATTRIBUTIONS,
    DataSource,
    DATE_CHANGE_TO_20TD,
    DEFAULT_POWER_KW,
    DEFAULT_TIMEOUT,
    REFERENCE_TZ,
    TARIFF2ID,
    TARIFFS,
    UTC_TZ,
    zoneinfo,
)
from aiopvpc.parser import extract_pvpc_data, get_url_prices
from aiopvpc.prices import make_price_sensor_attributes
from aiopvpc.pvpc_tariff import get_current_and_next_tariff_periods
from aiopvpc.utils import ensure_utc_time

_LOGGER = logging.getLogger(__name__)

# 🙈😱 Use randomized standard User-Agent info to avoid server banning 😖🤷
_STANDARD_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) "
        "Gecko/20100101 Firefox/47.3"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) "
        "Gecko/20100101 Firefox/43.4"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 11_3_1 like Mac OS X) "
        "AppleWebKit/603.1.30 (KHTML, like Gecko)"
    ),
    "Version/10.0 Mobile/14E304 Safari/602.1",
]


class PVPCData:
    """
    Data handler for PVPC hourly prices.

    * Async download of prices for each day
    * Generate state attributes for HA integration.

    - Prices are returned in a `Dict[datetime, float]`,
    with timestamps in UTC and prices in €/kWh.
    """

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        tariff: str = TARIFFS[0],
        local_timezone: Union[str, zoneinfo.ZoneInfo] = REFERENCE_TZ,
        power: float = DEFAULT_POWER_KW,
        power_valley: float = DEFAULT_POWER_KW,
        timeout: float = DEFAULT_TIMEOUT,
        data_source: DataSource = "apidatos",  # "esios_public",
    ):
        self.source_available = True
        self.state: Optional[float] = None
        self.state_available = False
        self.attributes: Dict[str, Any] = {}

        self.timeout = timeout
        self._session = session
        self._data_source = data_source
        self._user_agents = deque(sorted(_STANDARD_USER_AGENTS, key=lambda x: random()))

        self._local_timezone = zoneinfo.ZoneInfo(str(local_timezone))
        self.tariff = tariff
        if tariff not in TARIFFS:  # pragma: no cover
            _LOGGER.error("Unknown tariff '%s'. Should be one of %s", tariff, TARIFFS)
            self.tariff = TARIFFS[0]

        self._current_prices: Dict[datetime, float] = {}
        self._power = power
        self._power_valley = power_valley

    def _request_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._data_source == "apidatos":
            headers["Host"] = "apidatos.ree.es"
            return headers
        headers["Host"] = "api.esios.ree.es"
        headers["User-Agent"] = self._user_agents[0]
        # TODO add auth token
        # if self._data_source == "esios":
        return headers

    async def _api_get_prices(self, url: str, tariff: str) -> Dict[datetime, Any]:
        assert self._session is not None
        resp = await self._session.get(url, headers=self._request_headers())
        if resp.status < 400:
            data = await resp.json()
            return extract_pvpc_data(data, url, tariff, tz=self._local_timezone)
        elif resp.status == 403:  # pragma: no cover
            _LOGGER.warning("Forbidden error with '%s': %s", self._data_source, url)
            # loop user-agent and data-source
            self._user_agents.rotate()
            self._data_source = (
                "apidatos" if self._data_source == "esios_public" else "esios_public"
            )
        return {}

    async def _download_pvpc_prices(self, now: datetime) -> Dict[datetime, Any]:
        """
        PVPC data extractor.

        Make GET request to 'api.esios.ree.es' and extract hourly prices for
        the selected tariff from the JSON daily file download
        of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
        for the _Voluntary Price for Small Consumers_
        (Precio Voluntario para el Pequeño Consumidor, PVPC).

        Prices are referenced with datetimes in UTC.
        """
        assert now.date() >= DATE_CHANGE_TO_20TD, "No support for old tariffs"
        url = get_url_prices(self._data_source, self.tariff != TARIFFS[0], now)
        tariff = TARIFF2ID[self.tariff]
        try:
            async with async_timeout.timeout(2 * self.timeout):
                return await self._api_get_prices(url, tariff)
        except KeyError:
            _LOGGER.debug("Bad try on getting prices for %s", now)
        except asyncio.TimeoutError:
            if self.source_available:
                _LOGGER.warning("Timeout error requesting data from '%s'", url)
        except aiohttp.ClientError:
            if self.source_available:
                _LOGGER.warning("Client error in '%s'", url)
        return {}

    async def async_update_prices(self, now: datetime) -> Dict[datetime, float]:
        """
        Update electricity prices from the ESIOS API.

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        utc_now = ensure_utc_time(now)
        local_ref_now = utc_now.astimezone(REFERENCE_TZ)
        current_num_prices = len(self._current_prices)
        if local_ref_now.hour >= 20 and current_num_prices > 30:
            # already have today+tomorrow prices, avoid requests
            _LOGGER.debug(
                "Evening download avoided, now with %d prices from %s UTC",
                current_num_prices,
                list(self._current_prices)[0].strftime("%Y-%m-%d %Hh"),
            )
            return self._current_prices
        elif (
            local_ref_now.hour < 20
            and current_num_prices > 20
            and (
                list(self._current_prices)[-12].astimezone(REFERENCE_TZ).date()
                == local_ref_now.date()
            )
        ):
            # already have today prices, avoid request
            _LOGGER.debug(
                "Download avoided, now with %d prices up to %s UTC",
                current_num_prices,
                list(self._current_prices)[-1].strftime("%Y-%m-%d %Hh"),
            )
            return self._current_prices

        if current_num_prices and (
            list(self._current_prices)[0].astimezone(REFERENCE_TZ).date()
            == local_ref_now.date()
        ):
            # avoid download of today prices
            prices = self._current_prices.copy()
            _LOGGER.debug(
                "Avoided: %s, with %d prices -> last: %s, download-day: %s",
                local_ref_now,
                current_num_prices,
                list(self._current_prices)[0].astimezone(REFERENCE_TZ).date(),
                local_ref_now.date(),
            )
        else:
            txt_last = "--"
            if current_num_prices:
                txt_last = str(
                    list(self._current_prices)[-1].astimezone(self._local_timezone)
                )
            # make API call to download today prices
            _LOGGER.debug(
                "UN-Avoided: %s, with %d prices ->; last:%s, download-day: %s",
                local_ref_now,
                current_num_prices,
                txt_last,
                local_ref_now.date(),
            )
            prices = await self._download_pvpc_prices(local_ref_now)
            if not prices:
                return prices

        # At evening, it is possible to retrieve next day prices
        if local_ref_now.hour >= 20:
            next_day = local_ref_now + timedelta(days=1)
            prices_fut = await self._download_pvpc_prices(next_day)
            if prices_fut:
                prices.update(prices_fut)

        self._current_prices.update(prices)
        _LOGGER.debug(
            "Download done, now with %d prices from %s UTC",
            len(self._current_prices),
            list(self._current_prices)[0].strftime("%Y-%m-%d %Hh"),
        )

        return prices

    @property
    def attribution(self) -> str:
        """Return data-source attribution string."""
        return ATTRIBUTIONS[self._data_source]

    def process_state_and_attributes(self, utc_now: datetime) -> bool:
        """
        Generate the current state and sensor attributes.

        The data source provides prices in 0 to 24h sets, with correspondence
        with the main timezone in Spain. They are stored with UTC datetimes.

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        attributes: Dict[str, Any] = {
            "attribution": self.attribution,
            "tariff": self.tariff,
        }
        utc_time = ensure_utc_time(utc_now.replace(minute=0, second=0, microsecond=0))
        actual_time = utc_time.astimezone(self._local_timezone)
        # todo power_period/power_price €/kW*año
        if len(self._current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(REFERENCE_TZ).replace(hour=0).astimezone(UTC_TZ)
            )
            self._current_prices = {
                key_ts: price
                for key_ts, price in self._current_prices.items()
                if key_ts >= max_age
            }

        # set current price
        try:
            self.state = self._current_prices[utc_time]
            self.state_available = True
        except KeyError:
            self.state_available = False
            self.attributes = attributes
            return False

        # generate PVPC 2.0TD sensor attributes
        local_time = utc_time.astimezone(self._local_timezone)
        (current_period, next_period, delta,) = get_current_and_next_tariff_periods(
            local_time, zone_ceuta_melilla=self.tariff != TARIFFS[0]
        )
        attributes["period"] = current_period
        power = self._power_valley if current_period == "P3" else self._power
        attributes["available_power"] = int(1000 * power)
        attributes["next_period"] = next_period
        attributes["hours_to_next_period"] = int(delta.total_seconds()) // 3600

        # generate price attributes
        price_attrs = make_price_sensor_attributes(
            self._current_prices, utc_time, self._local_timezone
        )
        self.attributes = {**attributes, **price_attrs}
        return True
